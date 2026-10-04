"""
Generates a month-wise contribution line graph (last 12 months) as an SVG.

Usage (inside GitHub Actions):
    GH_USER=RutujaDeshmukh29 GH_TOKEN=<token> python scripts/monthly_graph.py

Local layout test without any token:
    python scripts/monthly_graph.py --demo

Only the Python standard library is used, so no pip install is needed.
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

MONTHS = 12
OUT_FILE = os.environ.get("OUT_FILE", "assets/monthly-contributions.svg")

# ---------- Theme (matches the dark README style) ----------
BG = "#0d1117"
GRID = "#21262d"
TEXT = "#c9d1d9"
MUTED = "#8b949e"
LINE = "#6366f1"
DOT = "#a78bfa"


def add_months(dt, n):
    """Return the first day of the month, n months after dt's month."""
    total = dt.year * 12 + (dt.month - 1) + n
    return dt.replace(year=total // 12, month=total % 12 + 1, day=1)


def month_ranges():
    """Return a list of (start, end) datetimes for the last MONTHS months, oldest first."""
    now = datetime.now(timezone.utc)
    this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    ranges = []
    for offset in range(-(MONTHS - 1), 1):
        start = add_months(this_month, offset)
        end = min(add_months(start, 1) - timedelta(seconds=1), now)
        ranges.append((start, end))
    return ranges


def fetch_counts(user, token, ranges):
    """Ask GitHub GraphQL for the contribution total of every month in one request."""
    iso = "%Y-%m-%dT%H:%M:%SZ"
    parts = []
    for i, (start, end) in enumerate(ranges):
        parts.append(
            f'm{i}: contributionsCollection(from: "{start.strftime(iso)}", '
            f'to: "{end.strftime(iso)}") '
            f"{{ contributionCalendar {{ totalContributions }} }}"
        )
    query = (
        "query($login: String!) { user(login: $login) { " + " ".join(parts) + " } }"
    )
    body = json.dumps({"query": query, "variables": {"login": user}}).encode()
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "monthly-contribution-graph",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.load(response)
    if "errors" in data or not data.get("data", {}).get("user"):
        print("GitHub API error:", json.dumps(data, indent=2))
        sys.exit(1)
    user_data = data["data"]["user"]
    return [
        user_data[f"m{i}"]["contributionCalendar"]["totalContributions"]
        for i in range(len(ranges))
    ]


def nice_max(value):
    """Round the top of the y-axis up to a clean number."""
    value = max(value, 4)
    for candidate in (4, 5, 8, 10, 20, 40, 50, 100, 200, 400, 500, 1000, 2000):
        if value <= candidate:
            return candidate
    return int(value * 1.2)


def render_svg(user, labels, years, counts):
    width, height = 900, 340
    left, right, top, bottom = 56, 36, 78, 62
    plot_w = width - left - right
    plot_h = height - top - bottom
    y_max = nice_max(max(counts))

    def x_at(i):
        return left + plot_w * i / (len(counts) - 1)

    def y_at(v):
        return top + plot_h - plot_h * v / y_max

    points = [(x_at(i), y_at(v)) for i, v in enumerate(counts)]
    line_path = " ".join(
        ("M" if i == 0 else "L") + f"{x:.1f},{y:.1f}" for i, (x, y) in enumerate(points)
    )
    area_path = (
        line_path
        + f" L{points[-1][0]:.1f},{top + plot_h} L{points[0][0]:.1f},{top + plot_h} Z"
    )

    total = sum(counts)
    best_i = max(range(len(counts)), key=lambda i: counts[i])

    out = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="Monthly contributions for the last {MONTHS} months">'
    )
    out.append(
        '<defs><linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{LINE}" stop-opacity="0.45"/>'
        f'<stop offset="100%" stop-color="{LINE}" stop-opacity="0"/>'
        "</linearGradient></defs>"
    )
    out.append(f'<rect width="{width}" height="{height}" rx="14" fill="{BG}"/>')
    out.append(
        f'<text x="{left}" y="36" fill="{TEXT}" font-size="20" font-weight="600" '
        f'font-family="Segoe UI, Helvetica, Arial, sans-serif">'
        f"Monthly Contributions</text>"
    )
    out.append(
        f'<text x="{left}" y="58" fill="{MUTED}" font-size="13" '
        f'font-family="Segoe UI, Helvetica, Arial, sans-serif">'
        f"@{user} · last {MONTHS} months · {total} total · best: "
        f"{labels[best_i]} ({counts[best_i]})</text>"
    )

    # Horizontal grid lines and y-axis labels
    for k in range(5):
        value = y_max * k / 4
        y = y_at(value)
        out.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" '
            f'stroke="{GRID}" stroke-width="1"/>'
        )
        label = f"{value:g}"
        out.append(
            f'<text x="{left - 10}" y="{y + 4:.1f}" fill="{MUTED}" font-size="11" '
            f'text-anchor="end" font-family="Segoe UI, Helvetica, Arial, sans-serif">'
            f"{label}</text>"
        )

    # Area, line, dots, value labels, month labels
    out.append(f'<path d="{area_path}" fill="url(#fill)"/>')
    out.append(
        f'<path d="{line_path}" fill="none" stroke="{LINE}" stroke-width="3" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
    )
    for i, (x, y) in enumerate(points):
        out.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="{BG}" '
            f'stroke="{DOT}" stroke-width="2.5"/>'
        )
        if counts[i] > 0:
            out.append(
                f'<text x="{x:.1f}" y="{y - 11:.1f}" fill="{TEXT}" font-size="11" '
                f'text-anchor="middle" '
                f'font-family="Segoe UI, Helvetica, Arial, sans-serif">{counts[i]}</text>'
            )
        out.append(
            f'<text x="{x:.1f}" y="{top + plot_h + 22}" fill="{MUTED}" font-size="12" '
            f'text-anchor="middle" '
            f'font-family="Segoe UI, Helvetica, Arial, sans-serif">{labels[i]}</text>'
        )
        if years[i]:
            out.append(
                f'<text x="{x:.1f}" y="{top + plot_h + 38}" fill="{MUTED}" '
                f'font-size="10" text-anchor="middle" opacity="0.7" '
                f'font-family="Segoe UI, Helvetica, Arial, sans-serif">{years[i]}</text>'
            )

    out.append("</svg>")
    return "\n".join(out)


def main():
    ranges = month_ranges()
    labels = [start.strftime("%b") for start, _ in ranges]
    # Show the year under the first month and under every January
    years = [
        str(start.year) if (i == 0 or start.month == 1) else ""
        for i, (start, _) in enumerate(ranges)
    ]

    if "--demo" in sys.argv:
        counts = [3, 8, 5, 12, 20, 9, 14, 6, 18, 25, 11, 16]
        user = "demo-user"
    else:
        user = os.environ.get("GH_USER")
        token = os.environ.get("GH_TOKEN")
        if not user or not token:
            print("Set GH_USER and GH_TOKEN, or run with --demo.")
            sys.exit(1)
        counts = fetch_counts(user, token, ranges)

    svg = render_svg(user, labels, years, counts)
    os.makedirs(os.path.dirname(OUT_FILE) or ".", exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"Wrote {OUT_FILE} — monthly counts: {counts}")


if __name__ == "__main__":
    main()
