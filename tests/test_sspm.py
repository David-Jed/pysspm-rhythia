"""
Tests for pysspm_rhythia.

These import the installed package directly. An earlier revision loaded
`pysspm.py` by path and registered it in `sys.modules` as "pysspm", which made
the suite pass while the real package was unimportable -- so every test here
must go through the public package entry points.
"""

import io
import struct

import pytest

import pysspm_rhythia
from pysspm_rhythia import SSPM, read_sspm
from pysspm_rhythia.parser import (
    AI_FINGERPRINT_FIELD,
    AI_GENERATED_FIELD,
    AI_GENERATOR_FIELD,
)

from conftest import build_v1_file, real_map_or_skip

# Byte offsets of the pointer table in a v2 file:
# header(10) + hash(20) + static metadata(18)
POINTER_TABLE_START = 10 + 20 + 18
POINTER_NAMES = ("custom_data", "audio", "cover", "marker_definitions", "markers")


def read_pointer(data, name):
    """Return (offset, length) for a named block in a v2 file."""
    index = POINTER_NAMES.index(name)
    return struct.unpack_from("<QQ", data, POINTER_TABLE_START + index * 16)


def as_plain_notes(notes):
    """Normalise notes to plain Python types for comparison."""
    return [(float(x), float(y), int(ms)) for x, y, ms in notes]


# --------------------------------------------------------------------------
# packaging
# --------------------------------------------------------------------------

def test_package_exposes_public_api():
    assert callable(pysspm_rhythia.read_sspm)
    assert pysspm_rhythia.SSPM is SSPM
    assert isinstance(pysspm_rhythia.__version__, str)


def test_reading_does_not_require_the_test_harness():
    """Regression: parser.py imported `pysspm`, which only existed under the old
    test harness, so `read_sspm` raised ModuleNotFoundError once installed."""
    chart = SSPM(difficulty="easy", map_name="X", mappers=["a"], notes=[(0, 0, 1)])
    assert read_sspm(io.BytesIO(chart.write(None))).map_name == "X"


# --------------------------------------------------------------------------
# round-trips
# --------------------------------------------------------------------------

@pytest.mark.parametrize("with_audio", [True, False])
@pytest.mark.parametrize("with_cover", [True, False])
def test_round_trip_all_block_combinations(notes, audio, png, with_audio, with_cover):
    expected_audio = audio if with_audio else b""
    expected_cover = png if with_cover else b""

    data = SSPM(
        difficulty="easy",
        map_name="Test run level",
        mappers=["Test_Pysspm_Rhythia", "Test"],
        notes=notes,
        audio_bytes=expected_audio,
        cover_bytes=expected_cover,
    ).write(None)

    chart = read_sspm(io.BytesIO(data))
    assert chart.audio_bytes == expected_audio
    assert chart.cover_bytes == expected_cover
    assert as_plain_notes(chart.notes) == sorted(as_plain_notes(notes), key=lambda n: n[2])


@pytest.mark.parametrize("with_audio", [True, False])
@pytest.mark.parametrize("with_cover", [True, False])
def test_pointers_address_the_real_blocks(notes, audio, png, with_audio, with_cover):
    """Regression: absent audio/cover blocks still advanced the running write
    offset by 8, so every later pointer was 8-16 bytes past its block and the
    marker pointer ran off the end of the file."""
    audio_bytes = audio if with_audio else b""
    cover_bytes = png if with_cover else b""

    data = SSPM(
        difficulty="easy", map_name="Pointers", mappers=["a"], notes=notes,
        audio_bytes=audio_bytes, cover_bytes=cover_bytes,
    ).write(None)

    definitions_offset, _ = read_pointer(data, "marker_definitions")
    # the definition block opens with a count byte then a length-prefixed "ssp_note"
    assert data[definitions_offset:definitions_offset + 3] == b"\x01\x08\x00"
    assert data[definitions_offset + 3:definitions_offset + 11] == b"ssp_note"

    marker_offset, marker_length = read_pointer(data, "markers")
    assert marker_offset + marker_length == len(data), "marker block overruns the file"

    audio_offset, audio_length = read_pointer(data, "audio")
    assert data[audio_offset:audio_offset + audio_length] == audio_bytes

    cover_offset, cover_length = read_pointer(data, "cover")
    assert data[cover_offset:cover_offset + cover_length] == cover_bytes


def test_absent_blocks_get_zeroed_pointers(notes):
    data = SSPM(difficulty="easy", map_name="Empty", mappers=["a"], notes=notes).write(None)
    assert read_pointer(data, "audio") == (0, 0)
    assert read_pointer(data, "cover") == (0, 0)


def test_quantum_notes_survive_round_trip(quantum_notes):
    chart = read_sspm(io.BytesIO(
        SSPM(difficulty="hard", map_name="Q", mappers=["a"], notes=quantum_notes).write(None)
    ))
    assert chart.quantum is True
    for (got_x, got_y, got_ms), (want_x, want_y, want_ms) in zip(
        chart.notes, sorted(quantum_notes, key=lambda n: n[2])
    ):
        assert got_ms == want_ms
        assert float(got_x) == pytest.approx(want_x, abs=1e-4)
        assert float(got_y) == pytest.approx(want_y, abs=1e-4)


def test_grid_notes_stay_integers(notes):
    chart = read_sspm(io.BytesIO(
        SSPM(difficulty="easy", map_name="G", mappers=["a"], notes=notes).write(None)
    ))
    assert chart.quantum is False


def test_notes_are_sorted_by_time(notes):
    chart = read_sspm(io.BytesIO(
        SSPM(difficulty="easy", map_name="S", mappers=["a"], notes=notes).write(None)
    ))
    timestamps = [int(note[2]) for note in chart.notes]
    assert timestamps == sorted(timestamps)


def test_last_ms_is_the_largest_timestamp(notes):
    chart = read_sspm(io.BytesIO(
        SSPM(difficulty="easy", map_name="L", mappers=["a"], notes=notes).write(None)
    ))
    assert chart.last_ms == max(note[2] for note in notes)


# --------------------------------------------------------------------------
# metadata
# --------------------------------------------------------------------------

def test_non_ascii_metadata_round_trips(notes):
    """Regression: string lengths were written as character counts, so any
    multi-byte name desynchronised the whole string block."""
    chart = read_sspm(io.BytesIO(SSPM(
        difficulty="easy",
        map_name="Cosmo キラー",
        song_name="星のカービィ",
        mappers=["ダビデ", "Test"],
        notes=notes,
    ).write(None)))

    assert chart.map_name == "Cosmo キラー"
    assert chart.song_name == "星のカービィ"
    assert chart.mappers == ["ダビデ", "Test"]


def test_map_rating_is_16_bit(notes):
    """Regression: the reader took `read(2)[0]`, truncating the rating to its
    low byte (300 came back as 44)."""
    chart = read_sspm(io.BytesIO(
        SSPM(difficulty="easy", map_name="R", mappers=["a"], notes=notes, map_rating=300).write(None)
    ))
    assert chart.map_rating == 300


@pytest.mark.parametrize("difficulty", ["na", "easy", "medium", "hard", "logic", "tasukete"])
def test_difficulty_round_trips(notes, difficulty):
    chart = read_sspm(io.BytesIO(
        SSPM(difficulty=difficulty, map_name="D", mappers=["a"], notes=notes).write(None)
    ))
    assert str(chart.difficulty) == difficulty


def test_writing_without_notes_is_rejected():
    with pytest.raises(ValueError):
        SSPM(difficulty="easy", map_name="N", mappers=["a"], notes=[]).write(None)


def test_bad_signature_is_rejected():
    with pytest.raises(TypeError):
        read_sspm(io.BytesIO(b"NOPE" + b"\x02\x00" + bytes(64)))


# --------------------------------------------------------------------------
# AI provenance tag
# --------------------------------------------------------------------------

def test_ai_tag_round_trips(notes):
    chart = SSPM(difficulty="easy", map_name="Generated", mappers=["bot"], notes=notes)
    chart.mark_ai_generated("my-gen/1.0")

    parsed = read_sspm(io.BytesIO(chart.write(None)))
    assert parsed.custom_data[AI_GENERATED_FIELD] == 1
    assert parsed.custom_data[AI_GENERATOR_FIELD] == "my-gen/1.0"
    assert parsed.custom_data[AI_FINGERPRINT_FIELD] == chart.compute_ai_fingerprint()


def test_ai_tag_hydrates_onto_attributes(notes):
    """Re-writing a tagged map must preserve the tag, not silently drop it."""
    chart = SSPM(difficulty="easy", map_name="G", mappers=["bot"], notes=notes)
    chart.mark_ai_generated("my-gen/1.0")

    parsed = read_sspm(io.BytesIO(chart.write(None)))
    assert parsed.ai_generated is True
    assert parsed.ai_generator == "my-gen/1.0"

    rewritten = read_sspm(io.BytesIO(parsed.write(None)))
    assert rewritten.ai_generated is True
    assert rewritten.custom_data[AI_FINGERPRINT_FIELD] == chart.ai_fingerprint


def test_fingerprint_tracks_notes_not_presentation(notes):
    """Retitling a generated map must not change its fingerprint; editing the
    notes must."""
    original = SSPM(difficulty="easy", map_name="A", mappers=["bot"], notes=notes)
    original.mark_ai_generated("gen/1")

    retitled = SSPM(difficulty="hard", map_name="Totally Different", mappers=["x"], notes=notes)
    retitled.mark_ai_generated("gen/1")

    edited = SSPM(difficulty="easy", map_name="A", mappers=["bot"], notes=notes + [(0, 0, 9000)])
    edited.mark_ai_generated("gen/1")

    assert retitled.ai_fingerprint == original.ai_fingerprint
    assert edited.ai_fingerprint != original.ai_fingerprint


def test_fingerprint_tracks_the_generator(notes):
    first = SSPM(difficulty="easy", map_name="A", mappers=["bot"], notes=notes)
    first.mark_ai_generated("gen-one/1")
    second = SSPM(difficulty="easy", map_name="A", mappers=["bot"], notes=notes)
    second.mark_ai_generated("gen-two/1")
    assert first.ai_fingerprint != second.ai_fingerprint


def test_untagged_maps_carry_no_ai_fields(notes):
    parsed = read_sspm(io.BytesIO(
        SSPM(difficulty="easy", map_name="Plain", mappers=["a"], notes=notes).write(None)
    ))
    assert parsed.ai_generated is False
    assert AI_GENERATED_FIELD not in parsed.custom_data


def test_mark_ai_generated_requires_a_generator(notes):
    chart = SSPM(difficulty="easy", map_name="A", mappers=["a"], notes=notes)
    with pytest.raises(ValueError):
        chart.mark_ai_generated("")


# --------------------------------------------------------------------------
# custom data
# --------------------------------------------------------------------------

def test_user_custom_fields_round_trip(notes):
    from pysspm_rhythia.parser import TYPE_STRING, TYPE_UINT32

    chart = SSPM(difficulty="easy", map_name="C", mappers=["a"], notes=notes)
    chart.custom_data["my_tool_notes"] = (TYPE_STRING, "generated at 120bpm")
    chart.custom_data["my_tool_seed"] = (TYPE_UINT32, 42)

    parsed = read_sspm(io.BytesIO(chart.write(None)))
    assert parsed.custom_data["my_tool_notes"] == "generated at 120bpm"
    assert parsed.custom_data["my_tool_seed"] == 42


def test_user_custom_fields_coexist_with_the_ai_tag(notes):
    from pysspm_rhythia.parser import TYPE_UINT32

    chart = SSPM(difficulty="easy", map_name="C", mappers=["a"], notes=notes)
    chart.custom_data["my_tool_seed"] = (TYPE_UINT32, 42)
    chart.mark_ai_generated("gen/1")

    parsed = read_sspm(io.BytesIO(chart.write(None)))
    assert parsed.custom_data["my_tool_seed"] == 42
    assert parsed.ai_generated is True
    assert parsed.custom_data[AI_GENERATOR_FIELD] == "gen/1"


# --------------------------------------------------------------------------
# SSPM v1
# --------------------------------------------------------------------------

def test_reads_v1_files(notes, png, audio):
    data = build_v1_file("abc123", "Artist - Song", ["Fog", "DigitalDemon"],
                         notes, cover=png, audio=audio)
    chart = read_sspm(io.BytesIO(data))

    assert chart.header.version == 1
    assert chart.map_id == "abc123"
    assert chart.map_name == "Artist - Song"
    assert chart.mappers == ["Fog", "DigitalDemon"]
    assert chart.cover_bytes == png
    assert chart.audio_bytes == audio
    assert as_plain_notes(chart.notes) == sorted(as_plain_notes(notes), key=lambda n: n[2])


def test_reads_v1_quantum_notes(quantum_notes):
    chart = read_sspm(io.BytesIO(
        build_v1_file("q", "Q", ["a"], quantum_notes)
    ))
    assert chart.quantum is True


def test_reads_v1_without_media(notes):
    chart = read_sspm(io.BytesIO(build_v1_file("m", "M", ["a"], notes)))
    assert chart.cover_bytes == b""
    assert chart.audio_bytes == b""
    assert len(chart.notes) == len(notes)


def test_v1_mappers_split_on_ampersand(notes):
    chart = read_sspm(io.BytesIO(build_v1_file("x", "X", ["Fog & Digital"], notes)))
    assert chart.mappers == ["Fog", "Digital"]


def test_v1_upconverts_to_v2(notes, png, audio):
    v1 = read_sspm(io.BytesIO(
        build_v1_file("abc", "Artist - Song", ["Fog"], notes, cover=png, audio=audio)
    ))
    v2 = read_sspm(io.BytesIO(v1.write(None)))

    assert v2.header.version == 2
    assert v2.map_name == v1.map_name
    assert v2.audio_bytes == audio
    assert v2.cover_bytes == png
    assert as_plain_notes(v2.notes) == as_plain_notes(v1.notes)


# --------------------------------------------------------------------------
# conversions
# --------------------------------------------------------------------------

def test_notes_to_text(notes):
    chart = read_sspm(io.BytesIO(
        SSPM(difficulty="easy", map_name="T", mappers=["a"], notes=notes).write(None)
    ))
    assert chart.NOTES2TEXT() == ",0|1|250,1|1|500,2|0|1500"


def test_has_audio_and_cover_helpers(notes, audio, png):
    chart = SSPM(difficulty="easy", map_name="H", mappers=["a"], notes=notes,
                 audio_bytes=audio, cover_bytes=png)
    assert chart.has_audio() and chart.has_cover()

    bare = SSPM(difficulty="easy", map_name="H", mappers=["a"], notes=notes)
    assert not bare.has_audio() and not bare.has_cover()


# --------------------------------------------------------------------------
# real-world maps (skipped when the optional assets are absent)
# --------------------------------------------------------------------------

def test_real_map_round_trip():
    path = real_map_or_skip("Test.sspm")
    original = read_sspm(str(path))
    rewritten = read_sspm(io.BytesIO(original.write(None)))

    assert as_plain_notes(rewritten.notes) == as_plain_notes(original.notes)
    assert rewritten.audio_bytes == original.audio_bytes
    assert rewritten.cover_bytes == original.cover_bytes
    assert rewritten.last_ms == original.last_ms
    assert rewritten.map_name == original.map_name
