#!/usr/bin/env python3
"""Reference encoder/decoder for the Zephyr range hood RF remote.

Protocol: 315 MHz OOK, 24-bit fixed code (PT2262/EV1527 style), unit T ~= 270 us.
  bit 0 = T on, 3T off
  bit 1 = 3T on, T off
  sync  = T on, 31T off   (sent after each 24-bit word)
Codes are 16-bit address + 8-bit command, sent MSB first.

Timings use the ESPHome remote_receiver convention: microseconds, positive for
carrier on (mark), negative for carrier off (space).

Usage:
  python3 tools/zephyr_rf.py decode captures/light_x4_2026-10-27.json
  python3 tools/zephyr_rf.py encode 0x051430
"""
from __future__ import annotations

import json
import sys

T_US = 270
WORD_BITS = 24

BUTTONS = {
    0x051430: "light",
    0x051403: "fan",
    0x05140C: "power",
    0x0514C0: "delay_off",
}


def _is_short(v: int) -> bool:
    return 120 <= v <= 480


def _is_long(v: int) -> bool:
    return 560 <= v <= 1100


def encode(code: int, repeats: int = 1, t_us: int = T_US) -> list[int]:
    """Return raw timings for `repeats` words of `code`."""
    if not 0 <= code < (1 << WORD_BITS):
        raise ValueError("code must fit in 24 bits")
    word: list[int] = []
    for b in range(WORD_BITS - 1, -1, -1):
        if (code >> b) & 1:
            word += [3 * t_us, -t_us]
        else:
            word += [t_us, -3 * t_us]
    word += [t_us, -31 * t_us]  # sync
    return word * repeats


def decode(timings: list[int]) -> list[int]:
    """Return every complete 24-bit word found in a capture, in order.

    Mirrors the ESPHome on_raw lambda in zephyr-hood.yaml.
    """
    words: list[int] = []
    bits = nbits = 0
    i, n = 0, len(timings)
    while i < n:
        mark = timings[i]
        if mark <= 0:
            bits = nbits = 0
            i += 1
            continue
        has_space = i + 1 < n and timings[i + 1] < 0
        space = -timings[i + 1] if has_space else 25000  # end of capture = idle
        if space >= 5000:
            if nbits == WORD_BITS and _is_short(mark):
                words.append(bits & 0xFFFFFF)
            bits = nbits = 0
        elif _is_long(mark) and _is_short(space):
            bits, nbits = (bits << 1) | 1, nbits + 1
        elif _is_short(mark) and _is_long(space):
            bits, nbits = bits << 1, nbits + 1
        else:
            bits = nbits = 0
        if nbits > WORD_BITS:
            bits = nbits = 0
        i += 2 if has_space else 1
    return words


def describe(code: int) -> str:
    addr, cmd = code >> 8, code & 0xFF
    name = BUTTONS.get(code, "unknown")
    return f"0x{code:06X}  address 0x{addr:04X}  command 0x{cmd:02X} ({cmd:08b})  {name}"


def _main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[1] == "decode":
        data = json.load(open(argv[2]))
        for idx, frame in enumerate(data["frames"], 1):
            words = decode(frame)
            uniq = sorted(set(words))
            print(f"frame {idx}: {len(words)} complete words")
            for c in uniq:
                print("   " + describe(c))
        return 0
    if len(argv) == 3 and argv[1] == "encode":
        code = int(argv[2], 0)
        print(describe(code))
        print(",".join(str(v) for v in encode(code)))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
