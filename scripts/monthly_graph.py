"""
Generates a contribution graph for the last 91 days (13 weeks) as one SVG:
  - Top panel:    DAILY contributions (line + area)
  - Bottom panel: WEEKLY totals (bars)

Usage (inside GitHub Actions):
    GH_USER=RutujaDeshmukh29 GH_TOKEN=<token> python scripts/monthly_graph.py

Local layout test without any token:
    python scripts/monthly_graph.py --demo

Only the Python standard library is used, so no pip install is needed.
The output file name stays the same as before, so your README link does not change.
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

DAYS = 91  # 13 full weeks (about 3 months)
OUT_FILE = os.environ.get("OUT_FILE", "assets/monthly-contributions.svg")

# ---------- Theme (matches the dark README style) ----------
BG = "#0d1117"
GRID = "#21262d"
TEXT = "#c9d1d9"
MUTED = "#8b949e"
LINE = "#6366f1"
DOT = "#a78bfa"
BAR = "#6366f1"
BAR_BEST = "#a78bfa"
FONT = "Segoe UI, Helvetica, Arial, sans-serif"


def short_date(d):
    return f"{d.strftime('%b')} {d.day}"


def fetch_days(user, token, start, end):
    """Return a list of DAYS integers: contributions for each day from start (oldest) to today."""
    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            weeks { contributionDays { date contributionCount } }
          }
        }
      }
    }
    """
    iso = "%Y-%m-%dT%H:%M:%SZ"
    body = json.dumps(
        {
            "query": query,
            "variables": {
                "login": user,
                "from": start.strftime(iso),
                "to": end.strftime(iso),
            },
        }
    ).encode()
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "contribution-graph",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.load(response)
    if "errors" in data or not data.get("data", {}).get("user"):
        print("GitHub API error:", json.dumps(data, indent=2))
        sys.exit(1)

    calendar = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    by_date = {}
    for week in calendar["weeks"]:
        for day in week["contributionDays"]:
            by_date[day["date"]] = day["contributionCount"]

    return [
        by_date.get((start + timedelta(days=i)).strftime("%Y-%m-%d"), 0)
        for i in range(DAYS)
    ]


def nice_max(value):
    """Round the top of the y-axis up to a clean number."""
    value = max(value, 4)
    for candidate in (4, 5, 8, 10, 15, 20, 30, 40, 50, 80, 100, 150, 200, 300, 500, 1000):
        if value <= candidate:
            return candidate
    return int(value * 1.2)


def longest_streak(counts):
    best = run = 0
    for c in counts:
        run = run + 1 if c > 0 else 0
        best = max(best, run)
    return best


def render_svg(user, start, counts):
    width, height = 900, 500
    left, right = 56, 36
    plot_w = width - left - right
    n = len(counts)
    dates = [start + timedelta(days=i) for i in range(n)]

    # Weekly totals: 7-day blocks from the start date
    weeks = []
    for k in range(0, n, 7):
        weeks.append((dates[k], sum(counts[k : k + 7])))

    total = sum(counts)
    active_days = sum(1 for c in counts if c > 0)
    streak = longest_streak(counts)
    best_day_i = max(range(n), key=lambda i: counts[i])
    best_week_i = max(range(len(weeks)), key=lambda i: weeks[i][1])

    out = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="Daily and weekly contributions for the last {n} days">'
    )
    out.append(
        '<defs><linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{LINE}" stop-opacity="0.45"/>'
        f'<stop offset="100%" stop-color="{LINE}" stop-opacity="0"/>'
        "</linearGradient></defs>"
    )
    out.append(f'<rect width="{width}" height="{height}" rx="14" fill="{BG}"/>')

    # ----- Title -----
    out.append(
        f'<text x="{left}" y="36" fill="{TEXT}" font-size="20" font-weight="600" '
        f'font-family="{FONT}">Contribution Activity · Last {n} Days</text>'
    )
    out.append(
        f'<text x="{left}" y="58" fill="{MUTED}" font-size="13" font-family="{FONT}">'
        f"@{user} · {total} contributions · {active_days} active days · "
        f"longest streak {streak} days · best day {short_date(dates[best_day_i])} "
        f"({counts[best_day_i]})</text>"
    )

    # ----- Panel 1: daily line -----
    top1, h1 = 104, 170
    y_max1 = nice_max(max(counts))

    def x_day(i):
        return left + plot_w * i / (n - 1)

    def y_day(v):
        return top1 + h1 - h1 * v / y_max1

    out.append(
        f'<text x="{left}" y="92" fill="{TEXT}" font-size="13" font-weight="600" '
        f'font-family="{FONT}">Daily contributions</text>'
    )
    for k in range(5):
        value = y_max1 * k / 4
        y = y_day(value)
        out.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" '
            f'stroke="{GRID}" stroke-width="1"/>'
        )
        out.append(
            f'<text x="{left - 10}" y="{y + 4:.1f}" fill="{MUTED}" font-size="11" '
            f'text-anchor="end" font-family="{FONT}">{value:g}</text>'
        )

    pts = [(x_day(i), y_day(c)) for i, c in enumerate(counts)]
    line_path = " ".join(
        ("M" if i == 0 else "L") + f"{x:.1f},{y:.1f}" for i, (x, y) in enumerate(pts)
    )
    area_path = f"{line_path} L{pts[-1][0]:.1f},{top1 + h1} L{pts[0][0]:.1f},{top1 + h1} Z"
    out.append(f'<path d="{area_path}" fill="url(#fill)"/>')
    out.append(
        f'<path d="{line_path}" fill="none" stroke="{LINE}" stroke-width="2.5" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
    )
    for i, (x, y) in enumerate(pts):
        if counts[i] > 0:
            radius = 4.5 if i == best_day_i else 3
            fill = DOT if i == best_day_i else BG
            out.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" fill="{fill}" '
                f'stroke="{DOT}" stroke-width="2"/>'
            )
    bx, by = pts[best_day_i]
    out.append(
        f'<text x="{bx:.1f}" y="{by - 10:.1f}" fill="{TEXT}" font-size="11" '
        f'text-anchor="middle" font-family="{FONT}">{counts[best_day_i]}</text>'
    )
    for i in range(0, n, 7):
        out.append(
            f'<text x="{x_day(i):.1f}" y="{top1 + h1 + 18}" fill="{MUTED}" '
            f'font-size="10" text-anchor="middle" font-family="{FONT}">'
            f"{short_date(dates[i])}</text>"
        )

    # ----- Panel 2: weekly bars -----
    top2, h2 = 356, 100
    y_max2 = nice_max(max(w[1] for w in weeks))
    slot = plot_w / len(weeks)
    bar_w = slot * 0.62

    out.append(
        f'<text x="{left}" y="326" fill="{TEXT}" font-size="13" font-weight="600" '
        f'font-family="{FONT}">Weekly totals</text>'
    )
    for k in range(5):
        value = y_max2 * k / 4
        y = top2 + h2 - h2 * value / y_max2
        out.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" '
            f'stroke="{GRID}" stroke-width="1"/>'
        )
        out.append(
            f'<text x="{left - 10}" y="{y + 4:.1f}" fill="{MUTED}" font-size="11" '
            f'text-anchor="end" font-family="{FONT}">{value:g}</text>'
        )
    for k, (week_start, week_total) in enumerate(weeks):
        cx = left + slot * (k + 0.5)
        bar_h = h2 * week_total / y_max2
        color = BAR_BEST if k == best_week_i else BAR
        if week_total > 0:
            out.append(
                f'<rect x="{cx - bar_w / 2:.1f}" y="{top2 + h2 - bar_h:.1f}" '
                f'width="{bar_w:.1f}" height="{bar_h:.1f}" rx="4" fill="{color}"/>'
            )
            out.append(
                f'<text x="{cx:.1f}" y="{top2 + h2 - bar_h - 6:.1f}" fill="{TEXT}" '
                f'font-size="11" text-anchor="middle" font-family="{FONT}">'
                f"{week_total}</text>"
            )
        out.append(
            f'<text x="{cx:.1f}" y="{top2 + h2 + 18}" fill="{MUTED}" font-size="10" '
            f'text-anchor="middle" font-family="{FONT}">{short_date(week_start)}</text>'
        )

    out.append("</svg>")
    return "\n".join(out)


def main():
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=DAYS - 1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    if "--demo" in sys.argv:
        pattern = [0, 2, 5, 0, 0, 8, 3, 1, 0, 6, 12, 4, 0, 0]
        counts = [pattern[i % len(pattern)] + (i % 5) for i in range(DAYS)]
        user = "demo-user"
    else:
        user = os.environ.get("GH_USER")
        token = os.environ.get("GH_TOKEN")
        if not user or not token:
            print("Set GH_USER and GH_TOKEN, or run with --demo.")
            sys.exit(1)
        counts = fetch_days(user, token, start, now)

    svg = render_svg(user, start, counts)
    os.makedirs(os.path.dirname(OUT_FILE) or ".", exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"Wrote {OUT_FILE} — {sum(counts)} contributions in the last {DAYS} days")


if __name__ == "__main__":
    main()
