"""Generate a coverage badge SVG from .coverage data.

Reads the total coverage percentage via the `coverage` API (no third-party
badge libraries needed) and writes a flat shields-style SVG.

Usage:
    # after running:  pytest --cov=backend
    .venv\\Scripts\\python.exe scripts\\generate_coverage_badge.py
"""
import os

import coverage

OUT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "docs", "coverage.svg"
)


def _color(pct: int) -> str:
    if pct >= 90:
        return "#4c1"  # brightgreen
    if pct >= 80:
        return "#97ca00"  # green
    if pct >= 70:
        return "#a4a61d"  # yellowgreen
    if pct >= 60:
        return "#dfb317"  # yellow
    if pct >= 50:
        return "#fe7d37"  # orange
    return "#e05d44"  # red


def _svg(pct: int) -> str:
    color = _color(pct)
    label = "coverage"
    value = f"{pct}%"
    # Approximate text widths for the flat badge layout.
    label_w = 62
    value_w = 38
    total_w = label_w + value_w
    label_x = label_w * 5  # centered in label region, scaled x10
    value_x = (label_w + value_w / 2) * 10
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="20" role="img" aria-label="{label}: {value}">
  <title>{label}: {value}</title>
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r"><rect width="{total_w}" height="20" rx="3" fill="#fff"/></clipPath>
  <g clip-path="url(#r)">
    <rect width="{label_w}" height="20" fill="#555"/>
    <rect x="{label_w}" width="{value_w}" height="20" fill="{color}"/>
    <rect width="{total_w}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="110" text-rendering="geometricPrecision">
    <text x="{label_x}" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)" textLength="{(label_w - 12) * 10}">{label}</text>
    <text x="{label_x}" y="140" transform="scale(.1)" fill="#fff" textLength="{(label_w - 12) * 10}">{label}</text>
    <text x="{value_x:.0f}" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)" textLength="{(value_w - 12) * 10}">{value}</text>
    <text x="{value_x:.0f}" y="140" transform="scale(.1)" fill="#fff" textLength="{(value_w - 12) * 10}">{value}</text>
  </g>
</svg>
"""


def main() -> None:
    cov = coverage.Coverage()
    cov.load()
    with open(os.devnull, "w") as devnull:
        total = cov.report(file=devnull)
    pct = round(total)
    with open(OUT_PATH, "w", encoding="utf-8") as handle:
        handle.write(_svg(pct))
    print(f"Wrote {OUT_PATH} ({pct}% coverage).")


if __name__ == "__main__":
    main()
