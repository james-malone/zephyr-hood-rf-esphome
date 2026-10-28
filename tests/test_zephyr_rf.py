"""Tests for tools/zephyr_rf.py. Run: python3 -m pytest tests"""
import json
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import zephyr_rf as z  # noqa: E402

CAPTURE = ROOT / "captures" / "light_x4_2026-10-27.json"


def test_real_light_captures_decode():
    frames = json.loads(CAPTURE.read_text())["frames"]
    assert len(frames) == 4
    for frame in frames:
        words = z.decode(frame)
        assert len(words) >= 6  # remote sends 7-8; the last is cut off by the capture buffer
        assert set(words) == {0x051430}


def test_round_trip_all_buttons():
    for code in z.BUTTONS:
        assert z.decode(z.encode(code, repeats=10)) == [code] * 10


def test_tolerates_timing_jitter():
    rng = random.Random(1)
    for code in z.BUTTONS:
        noisy = [int(v * rng.uniform(0.8, 1.2)) for v in z.encode(code, repeats=5)]
        assert z.decode(noisy) == [code] * 5


def test_rejects_garbage():
    rng = random.Random(2)
    junk = [rng.choice([1, -1]) * rng.randint(50, 3000) for _ in range(400)]
    assert z.decode(junk) == []
    assert z.decode([425, -2150] * 40) == []  # the 433 MHz neighbour sensor pattern


def test_command_structure():
    # one "11" pair per button, in a different slot of the command byte
    cmds = sorted(c & 0xFF for c in z.BUTTONS)
    assert cmds == [0x03, 0x0C, 0x30, 0xC0]
    assert {c >> 8 for c in z.BUTTONS} == {0x0514}
