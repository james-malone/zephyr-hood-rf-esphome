#!/usr/bin/env python3
"""Generate the protocol figures in docs/img/ (pure SVG, no dependencies)."""
from pathlib import Path

INK, INK2, BLUE, RED, PAPER, RULE = "#1C1B17", "#46433B", "#1F4E87", "#BF3326", "#FFFFFF", "#C9C6BC"
SANS = "Helvetica Neue, Helvetica, Arial, sans-serif"
MONO = "Menlo, Consolas, Courier New, monospace"
OUT = Path(__file__).resolve().parents[1] / "docs" / "img"


def svg(w, h, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'font-family="{SANS}">\n<rect width="{w}" height="{h}" fill="{PAPER}"/>\n{body}\n</svg>\n')


def text(x, y, s, size=12, fill=INK, anchor="start", weight="normal", family=SANS):
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" '
            f'font-weight="{weight}" font-family="{family}">{s}</text>')


def wave(x0, y_hi, y_lo, segs, px_per_t, color=BLUE, width=2):
    """segs: list of (level 1/0, units). Returns path + end x."""
    x, pts = x0, []
    lvl_prev = None
    for lvl, units in segs:
        y = y_hi if lvl else y_lo
        if lvl_prev is not None and lvl != lvl_prev:
            pts.append((x, y))
        elif lvl_prev is None:
            pts.append((x, y))
        x += units * px_per_t
        pts.append((x, y))
        lvl_prev = lvl
    d = "M" + " L".join(f"{a:.1f},{b:.1f}" for a, b in pts)
    return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}"/>', x


def dim(x1, x2, y, label, color=INK2):
    """Horizontal dimension line with end ticks and a centered label."""
    return (f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="{color}" stroke-width="0.8"/>'
            f'<line x1="{x1}" y1="{y-4}" x2="{x1}" y2="{y+4}" stroke="{color}" stroke-width="0.8"/>'
            f'<line x1="{x2}" y1="{y-4}" x2="{x2}" y2="{y+4}" stroke="{color}" stroke-width="0.8"/>'
            + text((x1 + x2) / 2, y + 15, label, 11, color, "middle", family=MONO))


def symbols_svg():
    T = 16  # px per unit
    parts = [text(24, 30, "LINE CODE", 11, BLUE, weight="bold"),
             text(24, 48, "One unit T = 270 µs. Every bit is 4T long; the sync pulse ends each 24-bit word.", 13, INK)]
    y_hi, y_lo = 100, 150
    groups = [("Bit 0", [(1, 1), (0, 3)], ["T", "3T"], BLUE),
              ("Bit 1", [(1, 3), (0, 1)], ["3T", "T"], BLUE),
              ("Sync", [(1, 1), (0, 31)], ["T", "31T = 8.4 ms"], RED)]
    x = 40
    for name, segs, labels, color in groups:
        parts.append(text(x, 84, name, 13, INK, weight="bold"))
        scale0 = T if name != "Sync" else 9
        path, x_end = wave(x - 14, y_hi, y_lo, [(0, 14 / scale0)] + segs, scale0, color)
        parts.append(path)
        # dimensions
        xx = x
        scale = T if name != "Sync" else 9
        for (lvl, units), lab in zip(segs, labels):
            parts.append(dim(xx, xx + units * scale, 172, lab))
            xx += units * scale
        x = x_end + 46
    parts.append(f'<line x1="24" y1="210" x2="{max(x - 20, 796)}" y2="210" stroke="{RULE}" stroke-width="0.8"/>')
    parts.append(text(24, 230, "Measured on 709 bits: short mark 270 ± 14 µs, long mark 815 ± 10 µs, "
                               "sync gap 8383 ± 8 µs. Carrier on = high.", 11, INK2, family=SANS))
    return svg(max(int(x - 4), 820), 246, "\n".join(parts))


def word_svg():
    code = 0x051430
    bits = f"{code:024b}"
    cw, x0, y0 = 30, 40, 92
    parts = [text(24, 30, "WORD FORMAT", 11, BLUE, weight="bold"),
             text(24, 48, "24 bits, most significant bit first: a 16-bit address, then an 8-bit command. "
                          "Shown: Light, 0x051430.", 13, INK)]
    for i, b in enumerate(bits):
        x = x0 + i * cw
        cmd = i >= 16
        fill = "#E7EDF5" if cmd else PAPER
        parts.append(f'<rect x="{x}" y="{y0}" width="{cw}" height="34" fill="{fill}" stroke="{INK}" stroke-width="0.8"/>')
        parts.append(text(x + cw / 2, y0 + 23, b, 15, RED if (cmd and b == "1") else INK, "middle", "bold", MONO))
        parts.append(text(x + cw / 2, y0 - 8, str(23 - i), 9, INK2, "middle", family=MONO))
    # sync box
    xs = x0 + 24 * cw + 8
    parts.append(f'<rect x="{xs}" y="{y0}" width="62" height="34" fill="{PAPER}" stroke="{RED}" stroke-width="1"/>')
    parts.append(text(xs + 31, y0 + 22, "SYNC", 12, RED, "middle", "bold"))
    # braces
    def brace(xa, xb, label, sub):
        y = y0 + 48
        return (f'<path d="M{xa},{y} L{xa},{y+6} L{xb},{y+6} L{xb},{y}" fill="none" stroke="{INK2}" stroke-width="0.8"/>'
                + text((xa + xb) / 2, y + 24, label, 12, INK, "middle", "bold")
                + text((xa + xb) / 2, y + 40, sub, 11, INK2, "middle", family=MONO))
    parts.append(brace(x0 + 2, x0 + 16 * cw - 2, "Address", "0x0514 (same for every button)"))
    parts.append(brace(x0 + 16 * cw + 2, x0 + 24 * cw - 2, "Command", "0x30"))
    parts.append(brace(xs, xs + 62, "Sync", "T + 31T"))
    # hex nibble labels
    for j in range(6):
        parts.append(text(x0 + j * 4 * cw + 2 * cw, y0 + 120, f"{bits[j*4:(j+1)*4]} = {int(bits[j*4:(j+1)*4], 2):X}",
                          10, INK2, "middle", family=MONO))
    return svg(xs + 62 + 30, 230, "\n".join(parts))


def burst_svg():
    T = 270e-6
    word_t = 128 * T
    px_per_ms = 2.6
    parts = [text(24, 30, "ONE BUTTON PRESS", 11, BLUE, weight="bold"),
             text(24, 48, "The remote sends the same 34.6 ms word back to back, 7 to 8 times (about 0.26 s per press).",
                  13, INK)]
    x0, y = 40, 90
    for k in range(8):
        x = x0 + k * word_t * 1e3 * px_per_ms
        w = 96 * T * 1e3 * px_per_ms  # data portion
        parts.append(f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="26" fill="{BLUE}"/>')
        g = 32 * T * 1e3 * px_per_ms
        parts.append(f'<line x1="{x+w:.1f}" y1="{y+26}" x2="{x+w+g:.1f}" y2="{y+26}" stroke="{RED}" stroke-width="2"/>')
        parts.append(text(x + w / 2, y + 17, f"{k+1}", 11, PAPER, "middle", "bold", MONO))
    end = x0 + 8 * word_t * 1e3 * px_per_ms
    parts.append(dim(x0, x0 + word_t * 1e3 * px_per_ms, y + 46, "34.6 ms"))
    parts.append(dim(x0, end, y + 82, "8 words ≈ 277 ms (ESPHome sends 10)"))
    parts.append(text(24, y + 128, "Blue: 24 data bits (25.9 ms). Red: sync gap (8.4 ms). "
                                   "There is no preamble, checksum, counter or rolling code.", 11, INK2))
    return svg(int(end) + 40, y + 144, "\n".join(parts))


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "line-code.svg").write_text(symbols_svg())
    (OUT / "word-format.svg").write_text(word_svg())
    (OUT / "press-burst.svg").write_text(burst_svg())
    print("wrote", ", ".join(p.name for p in sorted(OUT.glob("*.svg"))))
