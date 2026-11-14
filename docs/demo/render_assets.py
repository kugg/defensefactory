#!/usr/bin/env python3
"""Generate the deterministic SVG source frames for the README demo media."""

from pathlib import Path
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[2]
FRAME_DIR = ROOT / "docs/demo/frames"


FRAMES = [
    {
        "eyebrow": "01 · REPORT",
        "flow": ["BUG REPORT", "DURABLE TICKET"],
        "title": "The ticket is the ledger",
        "body": [
            ("finding", "FIX-1 · Credential reaches peer"),
            ("state", "active · exact subject and scope retained"),
            ("receipt", "inputs and decisions survive the handoff"),
        ],
        "console": "report  FIX-1 [active] · Credential reaches peer",
    },
    {
        "eyebrow": "02 · ASSESS",
        "flow": ["TICKET", "QUALIFY", "BUG CLASS"],
        "title": "One bug becomes a systems question",
        "body": [
            ("claim", "PEER-AUTH"),
            ("invariant", "CREDENTIAL-TO-UNVERIFIED-PEER"),
            ("class", "FIX-1 current + FIX-2 historical"),
        ],
        "console": "assess  claim PEER-AUTH · 2 evaluated variants",
    },
    {
        "eyebrow": "03 · REPAIR",
        "flow": ["BUG CLASS", "ARCHITECTURAL REPAIR", "HARD FENCE"],
        "title": "Repair the boundary, not only the symptom",
        "body": [
            ("paths", "primary · retry · fallback"),
            ("also", "alternate constructor · configuration"),
            ("fence", "PEER-IDENTITY-FENCE · PEER-REGRESSION"),
        ],
        "console": "repair  restores PEER-AUTH across every declared path",
    },
    {
        "eyebrow": "04 · VERIFY + DELIVER",
        "flow": ["EXACT MERGE SUBJECT", "VERIFY", "DRAFT PR"],
        "title": "The proof follows the candidate",
        "body": [
            ("subject", "fixture/repository @ cccccccc…"),
            ("result", "class remediated within declared scope"),
            ("proof", "2/2 variants + claim + hard fence"),
        ],
        "console": "delivery  PR proof section generated · subject retained",
    },
    {
        "eyebrow": "05 · LEARN",
        "flow": ["FROZEN EVIDENCE", "SUGGESTION", "NEXT VERSION"],
        "title": "Failures improve the next factory run",
        "body": [
            ("rule", "Credentials must not cross to an unverified peer."),
            ("change", "version the rule, contract and fence"),
            ("history", "previous trial evidence remains unchanged"),
        ],
        "console": "next  fresh attempt · stronger architectural gradient",
    },
]


def flow_markup(items):
    x = 70
    blocks = []
    for index, item in enumerate(items):
        width = max(210, min(420, 28 + len(item) * 15))
        blocks.append(
            f'<rect x="{x}" y="172" width="{width}" height="72" rx="4" '
            'fill="#fff"/>'
            f'<text x="{x + width / 2}" y="217" text-anchor="middle" '
            'fill="#000" font-family="Arial, Helvetica, sans-serif" '
            f'font-size="22" font-weight="700">{escape(item)}</text>'
        )
        x += width
        if index < len(items) - 1:
            blocks.append(
                f'<path d="M{x + 14} 208h56m-18-16 18 16-18 16" '
                'fill="none" stroke="#fff" stroke-width="5"/>'
            )
            x += 92
    return "\n".join(blocks)


def frame_svg(number, frame):
    rows = []
    y = 390
    for label, value in frame["body"]:
        rows.append(
            f'<text x="76" y="{y}" fill="#7d7d7d" font-family="Menlo, Consolas, monospace" '
            f'font-size="23">{escape(label):12}</text>'
            f'<text x="270" y="{y}" fill="#fff" font-family="Menlo, Consolas, monospace" '
            f'font-size="23">{escape(value)}</text>'
        )
        y += 52
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" role="img">
  <rect width="1280" height="720" fill="#000"/>
  <rect x="28" y="28" width="1224" height="664" rx="10" fill="none" stroke="#333" stroke-width="2"/>
  <text x="70" y="82" fill="#fff" font-family="Arial, Helvetica, sans-serif" font-size="24" font-weight="700" letter-spacing="3">DARK FACTORY</text>
  <text x="1210" y="82" text-anchor="end" fill="#777" font-family="Menlo, Consolas, monospace" font-size="18">SYNTHETIC HELPER DEMO · {number}/5</text>
  <text x="70" y="132" fill="#777" font-family="Menlo, Consolas, monospace" font-size="18">OFFLINE DETERMINISTIC FIXTURE · NO MODEL OR SERVICE CALLS</text>
  {flow_markup(frame["flow"])}
  <text x="70" y="319" fill="#777" font-family="Arial, Helvetica, sans-serif" font-size="18" font-weight="700" letter-spacing="2">{escape(frame["eyebrow"])}</text>
  <text x="70" y="357" fill="#fff" font-family="Arial, Helvetica, sans-serif" font-size="31" font-weight="700">{escape(frame["title"])}</text>
  {''.join(rows)}
  <rect x="58" y="578" width="1164" height="72" rx="4" fill="#111" stroke="#333"/>
  <circle cx="86" cy="614" r="6" fill="#fff"/>
  <text x="106" y="622" fill="#fff" font-family="Menlo, Consolas, monospace" font-size="20">{escape(frame["console"])}</text>
  <text x="70" y="677" fill="#666" font-family="Arial, Helvetica, sans-serif" font-size="15">Synthetic metadata and execution evidence only · no live product, source index, PR mutation or deployment claim</text>
</svg>
'''


def main():
    FRAME_DIR.mkdir(parents=True, exist_ok=True)
    for number, frame in enumerate(FRAMES, start=1):
        target = FRAME_DIR / f"{number:02d}.svg"
        target.write_text(frame_svg(number, frame), encoding="utf-8")
        print(target.relative_to(ROOT))


if __name__ == "__main__":
    main()
