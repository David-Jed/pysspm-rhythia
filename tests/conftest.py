"""
Shared fixtures.

Fixtures are synthesised in-process rather than loaded from committed binaries,
so the suite runs on a clean checkout (and in CI) with no large media assets.
Tests that need the real-world maps in `tests/` skip themselves when absent.
"""

import base64
import struct
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).parent

# A valid 1x1 transparent PNG -- the library stores covers verbatim, so the
# image only has to be a real PNG, not a large one.
TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

# The library treats audio as an opaque blob, so a stub stands in for an MP3.
FAKE_AUDIO = b"ID3\x03\x00\x00\x00" + b"\xff\xfb\x90\x00" * 64


@pytest.fixture
def notes():
    """Deliberately out of time order -- readers and writers must sort."""
    return [(1, 1, 500), (0, 1, 250), (2, 0, 1500)]


@pytest.fixture
def quantum_notes():
    return [(1.2345, 0.5, 100), (2, 0, 200), (0.75, 1.25, 3000)]


@pytest.fixture
def png():
    return TINY_PNG


@pytest.fixture
def audio():
    return FAKE_AUDIO


def build_v1_file(map_id, map_name, mappers, notes, difficulty=0x03, cover=b"", audio=b""):
    """
    Build an SSPM v1 file byte-for-byte from the v1 spec.

    Used because the library cannot write v1, so a v1 reader test needs an
    independently-constructed fixture rather than a round-trip.
    https://github.com/basils-garden/types/blob/main/sspm/v1.md
    """
    data = bytearray(b"\x53\x53\x2b\x6d" + b"\x01\x00" + b"\x00\x00")

    for text in (map_id, map_name, ", ".join(mappers)):
        data += text.encode("utf-8") + b"\n"

    data += struct.pack("<I", max(note[2] for note in notes))
    data += struct.pack("<I", len(notes))
    data += bytes([difficulty])

    data += (b"\x02" + struct.pack("<Q", len(cover)) + cover) if cover else b"\x00"
    data += (b"\x01" + struct.pack("<Q", len(audio)) + audio) if audio else b"\x00"

    for note_x, note_y, note_ms in notes:
        data += struct.pack("<I", note_ms)
        if float(note_x).is_integer() and float(note_y).is_integer():
            data += b"\x00" + bytes([int(note_x), int(note_y)])
        else:
            data += b"\x01" + struct.pack("<ff", note_x, note_y)

    return bytes(data)


def real_map_or_skip(name):
    """Return a path to a committed real-world map, or skip the test."""
    path = TESTS_DIR / name
    if not path.exists():
        pytest.skip(f"optional real-world fixture {name} not present")
    return path
