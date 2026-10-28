#!/usr/bin/env python3
"""Build docs/zephyr-rf-protocol.pdf from docs/src/zephyr-rf-protocol.md with the Sterling renderer.

Usage: python3 tools/build_pdf.py /path/to/sterling/scripts/render.py
The {{FIG:name}} placeholders are replaced with the SVGs in docs/img/, restyled for the PDF.
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAPTIONS = {
    "line-code": "Line code. One unit T is 270 microseconds; carrier on is drawn high.",
    "word-format": "Word format, shown for the Light code 0x051430. Command bits set to one are in red.",
    "press-burst": "One press: the same 34.6 ms word sent back to back. Blue is data, red is the sync gap.",
}


def pdf_svg(name: str) -> str:
    s = (ROOT / "docs" / "img" / f"{name}.svg").read_text()
    s = re.sub(r'<rect width="\d+" height="\d+" fill="#FFFFFF"/>\n', "", s)          # page supplies the paper
    s = re.sub(r'<text x="24" y="(30|48)".*?</text>', "", s)                           # titles become captions
    s = s.replace("Helvetica Neue, Helvetica, Arial, sans-serif", "Heros, sans-serif")
    s = s.replace("Menlo, Consolas, Courier New, monospace", "Cursor, monospace")
    m = re.search(r'viewBox="0 0 (\d+) (\d+)" width="\d+" height="\d+"', s)
    w, h = int(m.group(1)), int(m.group(2))
    s = s.replace(m.group(0), f'viewBox="0 60 {w} {h - 60}"')
    s = s.replace('<?xml version="1.0"?>', "")
    return (f'<figure class="full">{s.strip()}<figcaption><span class="lab" data-kind="figure"></span> '
            f'{CAPTIONS[name]}</figcaption></figure>')


def main() -> int:
    render = Path(sys.argv[1])
    src = (ROOT / "docs" / "src" / "zephyr-rf-protocol.md").read_text()
    src = re.sub(r"\{\{FIG:([a-z-]+)\}\}", lambda m: pdf_svg(m.group(1)), src)
    with tempfile.TemporaryDirectory() as tmp:
        md = Path(tmp) / "zephyr-rf-protocol.md"
        md.write_text(src)
        out = ROOT / "docs" / "zephyr-rf-protocol.pdf"
        subprocess.run([sys.executable, str(render), str(md), str(out)], check=True)
    print("wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
