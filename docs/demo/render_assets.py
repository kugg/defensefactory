#!/usr/bin/env python3
"""Generate persistent light/dark flow frames for the README demo animation."""

import json
from pathlib import Path
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[2]
FRAME_DIR = ROOT / "docs/demo/frames"
RECORD = ROOT / "docs/demo/synthetic-trial.json"


STEPS = [
    ("REPORT", "Capture bug"),
    ("INTAKE", "Freeze scope"),
    ("ASSESS", "Qualify finding"),
    ("REPAIR", "Restore boundary"),
    ("VERIFY", "Prove candidate"),
    ("DRAFT PR", "Carry proof"),
]


THEMES = {
    "dark": {
        "background": "#020806",
        "border": "#0b5d2a",
        "title": "#effff4",
        "muted": "#789582",
        "future_fill": "#101713",
        "future_stroke": "#35513f",
        "future_text": "#819488",
        "done_fill": "#0b3d1c",
        "done_stroke": "#1db954",
        "done_text": "#caffd7",
        "active_fill": "#39ff78",
        "active_text": "#001a08",
        "track": "#25352b",
        "scan": "#8affad",
        "scan_opacity": "0.035",
    },
    "light": {
        "background": "#f5fff7",
        "border": "#8fc9a2",
        "title": "#102b18",
        "muted": "#587061",
        "future_fill": "#edf5ef",
        "future_stroke": "#afc7b6",
        "future_text": "#66766b",
        "done_fill": "#dff5e6",
        "done_stroke": "#20864a",
        "done_text": "#0b5028",
        "active_fill": "#006b2d",
        "active_text": "#ffffff",
        "track": "#adc7b5",
        "scan": "#087a38",
        "scan_opacity": "0.055",
    },
}


def node_markup(index, active, theme):
    x = 40 + index * 204
    y = 260
    width = 170
    height = 120
    name, purpose = STEPS[index]
    if index < active:
        fill = theme["done_fill"]
        stroke = theme["done_stroke"]
        text = theme["done_text"]
        opacity = "1"
    elif index == active:
        fill = theme["active_fill"]
        stroke = theme["active_fill"]
        text = theme["active_text"]
        opacity = "1"
    else:
        fill = theme["future_fill"]
        stroke = theme["future_stroke"]
        text = theme["future_text"]
        opacity = "0.88"
    glow = ' filter="url(#phosphor-glow)"' if index == active else ""
    return f'''
    <g opacity="{opacity}"{glow}>
      <rect x="{x}" y="{y}" width="{width}" height="{height}" rx="8" fill="{fill}" stroke="{stroke}" stroke-width="3"/>
      <text x="{x + width / 2}" y="{y + 48}" text-anchor="middle" fill="{text}" font-family="Arial, Helvetica, sans-serif" font-size="22" font-weight="700">{escape(name)}</text>
      <text x="{x + width / 2}" y="{y + 82}" text-anchor="middle" fill="{text}" font-family="Arial, Helvetica, sans-serif" font-size="18">{escape(purpose)}</text>
    </g>'''


def connector_markup(index, active, theme):
    x1 = 210 + index * 204
    x2 = 244 + index * 204
    color = theme["done_stroke"] if index < active else theme["track"]
    return f'<path d="M{x1} 320h{x2 - x1}m-12-10 12 10-12 10" fill="none" stroke="{color}" stroke-width="4"/>'


def frame_svg(number, theme_name, ticket):
    active = number - 1
    theme = THEMES[theme_name]
    nodes = []
    for index in range(len(STEPS)):
        nodes.append(node_markup(index, active, theme))
        if index < len(STEPS) - 1:
            nodes.append(connector_markup(index, active, theme))

    ticket_x = 40 + active * 204 + 20
    current_name, current_purpose = STEPS[active]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" role="img" aria-labelledby="title desc">
  <title id="title">Defense Factory ticket flow: {escape(current_name)}</title>
  <desc id="desc">A persistent six-step flow with {escape(current_name)} highlighted: {escape(current_purpose)}.</desc>
  <defs>
    <filter id="phosphor-glow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur in="SourceGraphic" stdDeviation="3" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <pattern id="scanlines" width="4" height="4" patternUnits="userSpaceOnUse">
      <path d="M0 3.5h4" stroke="{theme['scan']}" stroke-opacity="{theme['scan_opacity']}"/>
    </pattern>
  </defs>
  <rect width="1280" height="720" fill="{theme['background']}"/>
  <rect x="24" y="24" width="1232" height="672" rx="12" fill="none" stroke="{theme['border']}" stroke-width="2"/>
  <rect width="1280" height="720" fill="url(#scanlines)"/>

  <text x="52" y="78" fill="{theme['title']}" font-family="Arial, Helvetica, sans-serif" font-size="28" font-weight="700" letter-spacing="2">ONE TICKET · SIX DURABLE HANDOFFS</text>
  <text x="1228" y="78" text-anchor="end" fill="{theme['muted']}" font-family="Menlo, Consolas, monospace" font-size="18">{number:02d} / 06</text>
  <text x="52" y="116" fill="{theme['muted']}" font-family="Menlo, Consolas, monospace" font-size="17">OFFLINE DETERMINISTIC FIXTURE · NO MODEL OR SERVICE CALLS</text>

  <g filter="url(#phosphor-glow)">
    <rect x="{ticket_x}" y="174" width="130" height="48" rx="24" fill="{theme['active_fill']}"/>
    <text x="{ticket_x + 65}" y="205" text-anchor="middle" fill="{theme['active_text']}" font-family="Menlo, Consolas, monospace" font-size="17" font-weight="700">TICKET {escape(ticket)}</text>
    <path d="M{ticket_x + 65} 222v28" stroke="{theme['active_fill']}" stroke-width="4"/>
  </g>

  {''.join(nodes)}

  <text x="640" y="474" text-anchor="middle" fill="{theme['muted']}" font-family="Menlo, Consolas, monospace" font-size="18">CURRENT HANDOFF</text>
  <text x="640" y="520" text-anchor="middle" fill="{theme['active_fill']}" font-family="Arial, Helvetica, sans-serif" font-size="34" font-weight="700">{escape(current_name)} · {escape(current_purpose)}</text>

  <path d="M160 592h960" stroke="{theme['track']}" stroke-width="2"/>
  <text x="640" y="632" text-anchor="middle" fill="{theme['title']}" font-family="Menlo, Consolas, monospace" font-size="19">EXACT SUBJECT  ·  EVIDENCE  ·  LIMITATIONS  ·  NEXT ACTION</text>
  <text x="640" y="674" text-anchor="middle" fill="{theme['muted']}" font-family="Arial, Helvetica, sans-serif" font-size="15">Synthetic helper evidence only · no live product, source index, PR mutation or deployment claim</text>
</svg>
'''


def main():
    record = json.loads(RECORD.read_text(encoding="utf-8"))
    ticket = record["report"]["ticket"]
    for stale in FRAME_DIR.glob("*.svg"):
        stale.unlink()
    for theme_name in THEMES:
        target_dir = FRAME_DIR / theme_name
        target_dir.mkdir(parents=True, exist_ok=True)
        for stale in target_dir.glob("*.svg"):
            stale.unlink()
        for number in range(1, len(STEPS) + 1):
            target = target_dir / f"{number:02d}.svg"
            target.write_text(frame_svg(number, theme_name, ticket), encoding="utf-8")
            print(target.relative_to(ROOT))


if __name__ == "__main__":
    main()
