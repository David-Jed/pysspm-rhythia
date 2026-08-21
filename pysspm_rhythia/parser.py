"""
Binary readers/writers for the SSPM container.

Layouts follow the upstream specs:
- v2: https://github.com/basils-garden/types/blob/main/sspm/v2.md
- v1: https://github.com/basils-garden/types/blob/main/sspm/v1.md

Soon-to-be-supported Pheonyx & video formats. (once I find specs)
"""

from hashlib import sha1
from typing import BinaryIO, Dict, Tuple
from warnings import warn

import numpy as np

from pysspm_rhythia.pysspm import SSPM, Header

# Custom data / marker value type IDs (v2 spec, "Data type values")
TYPE_END          = 0x00
TYPE_INT8         = 0x01
TYPE_UINT16       = 0x02
TYPE_UINT32       = 0x03
TYPE_UINT64       = 0x04
TYPE_FLOAT32      = 0x05
TYPE_FLOAT64      = 0x06
TYPE_POSITION     = 0x07
TYPE_BUFFER       = 0x08
TYPE_STRING       = 0x09
TYPE_LONG_BUFFER  = 0x0a
TYPE_LONG_STRING  = 0x0b
TYPE_ARRAY        = 0x0c

# Custom data field IDs used to fingerprint machine-generated maps.
# Conformant readers skip unknown custom data fields, so these stay compatible
# with Rhythia / SS+ / SSQE.
AI_GENERATED_FIELD   = "ai_generated"
AI_GENERATOR_FIELD   = "ai_generator"
AI_FINGERPRINT_FIELD = "ai_fingerprint"


def _read_length_prefixed_string(data: BinaryIO, fourbytes: bool = False, encoding: str = "utf-8") -> str:
    """Read a uint16 (or uint32) length-prefixed string. Falls back to latin-1 on bad UTF-8."""
    size = 4 if fourbytes else 2
    length = int.from_bytes(data.read(size), byteorder="little")
    raw = data.read(length)
    try:
        return raw.decode(encoding)
    except UnicodeDecodeError:
        # SS+ historically wrote ASCII; latin-1 never raises and round-trips bytes.
        return raw.decode("latin-1")


def _write_length_prefixed_string(value: str, fourbytes: bool = False) -> bytes:
    """Encode a string with its *byte* length prefixed (not its character count)."""
    encoded = value.encode("utf-8")
    return len(encoded).to_bytes(4 if fourbytes else 2, "little") + encoded


def _read_newline_terminated_string(data: BinaryIO, encoding: str = "utf-8") -> str:
    """Read a newline-terminated string (v1 metadata encoding)."""
    buffer = bytearray()
    while True:
        char = data.read(1)
        if not char or char == b"\n":
            break
        buffer.extend(char)
    try:
        return buffer.decode(encoding)
    except UnicodeDecodeError:
        return buffer.decode("latin-1")


def _read_typed_value(data: BinaryIO, type_id: int, array_type: int = None):
    """Read one custom-data value of the given spec type ID."""
    match type_id:
        case 0x00:  # TYPE_END
            return None
        case 0x01:  # int8
            return int.from_bytes(data.read(1), "little", signed=True)
        case 0x02:  # uint16
            return int.from_bytes(data.read(2), "little")
        case 0x03:  # uint32
            return int.from_bytes(data.read(4), "little")
        case 0x04:  # uint64
            return int.from_bytes(data.read(8), "little")
        case 0x05:  # float32
            return float(np.frombuffer(data.read(4), dtype=np.float32)[0])
        case 0x06:  # float64
            return float(np.frombuffer(data.read(8), dtype=np.float64)[0])
        case 0x07:  # position -> (x, y)
            if int.from_bytes(data.read(1), "little") == 0:
                return (int.from_bytes(data.read(1), "little"), int.from_bytes(data.read(1), "little"))
            return (
                float(np.frombuffer(data.read(4), dtype=np.float32)[0]),
                float(np.frombuffer(data.read(4), dtype=np.float32)[0]),
            )
        case 0x08:  # buffer
            return data.read(int.from_bytes(data.read(2), "little"))
        case 0x09:  # string
            return _read_length_prefixed_string(data)
        case 0x0a:  # long buffer
            return data.read(int.from_bytes(data.read(4), "little"))
        case 0x0b:  # long string
            return _read_length_prefixed_string(data, fourbytes=True)
        case 0x0c:  # array
            data.read(4)  # total byte length, excluding these 4 bytes
            count = int.from_bytes(data.read(2), "little")
            return [_read_typed_value(data, array_type) for _ in range(count)]
        case _:
            raise ValueError(f"Unknown SSPM data type ID: {hex(type_id)}")


def _write_typed_value(value, type_id: int) -> bytes:
    """Encode one custom-data value. Mirrors `_read_typed_value`."""
    match type_id:
        case 0x01:
            return int(value).to_bytes(1, "little", signed=True)
        case 0x02:
            return int(value).to_bytes(2, "little")
        case 0x03:
            return int(value).to_bytes(4, "little")
        case 0x04:
            return int(value).to_bytes(8, "little")
        case 0x05:
            return np.float32(value).tobytes()
        case 0x06:
            return np.float64(value).tobytes()
        case 0x08:
            return len(value).to_bytes(2, "little") + bytes(value)
        case 0x09:
            return _write_length_prefixed_string(value)
        case 0x0a:
            return len(value).to_bytes(4, "little") + bytes(value)
        case 0x0b:
            return _write_length_prefixed_string(value, fourbytes=True)
        case _:
            raise ValueError(f"Unsupported SSPM custom data type for writing: {hex(type_id)}")


def _read_custom_data(data: BinaryIO) -> Dict[str, object]:
    """Read the custom data block into a plain dict of field ID -> value."""
    fields = {}
    field_count = int.from_bytes(data.read(2), "little")

    for _ in range(field_count):
        field_id = _read_length_prefixed_string(data)
        type_id = int.from_bytes(data.read(1), "little")
        array_type = int.from_bytes(data.read(1), "little") if type_id == TYPE_ARRAY else None
        fields[field_id] = _read_typed_value(data, type_id, array_type)

    return fields


def _write_custom_data(fields: Dict[str, Tuple[int, object]]) -> bytes:
    """Write a custom data block from field ID -> (type_id, value)."""
    block = bytearray(len(fields).to_bytes(2, "little"))
    for field_id, (type_id, value) in fields.items():
        block.extend(_write_length_prefixed_string(field_id))
        block.append(type_id)
        block.extend(_write_typed_value(value, type_id))
    return bytes(block)


def _read_notes(data: BinaryIO, note_count: int, skip_marker_type: bool) -> Tuple[list, bool]:
    """Read `note_count` note markers. Returns (notes sorted by ms, is_quantum)."""
    notes = []
    is_quantum = False

    for _ in range(note_count):
        ms = int.from_bytes(data.read(4), "little")
        if skip_marker_type:
            data.read(1)  # v2 marker type byte; notes are always type 0

        if int.from_bytes(data.read(1), "little") == 0:
            x = int.from_bytes(data.read(1), "little")
            y = int.from_bytes(data.read(1), "little")
        else:
            is_quantum = True
            x = float(np.frombuffer(data.read(4), dtype=np.float32)[0])
            y = float(np.frombuffer(data.read(4), dtype=np.float32)[0])

        notes.append((x, y, np.uint32(ms)))

    return sorted(notes, key=lambda note: note[2]), is_quantum


def _ProcessSSPMV2(fileBytes: BinaryIO, header: Header, _use_strict: bool = False) -> SSPM:
    """Parse an SSPM v2 body. The 10-byte header must already be consumed."""

    # --- static metadata ---
    note_hash    = fileBytes.read(20)
    last_ms      = int.from_bytes(fileBytes.read(4), "little")
    note_count   = int.from_bytes(fileBytes.read(4), "little")
    marker_count = int.from_bytes(fileBytes.read(4), "little")

    difficulty     = fileBytes.read(1)[0]
    map_rating     = int.from_bytes(fileBytes.read(2), "little")  # 16 bit uint
    contains_audio = fileBytes.read(1)[0] == 1
    contains_cover = fileBytes.read(1)[0] == 1
    requires_mod   = fileBytes.read(1)[0] == 1

    # --- pointers (offset/length pairs, 0 when the block is absent) ---
    def _pointer() -> Tuple[int, int]:
        offset = int.from_bytes(fileBytes.read(8), "little")
        length = int.from_bytes(fileBytes.read(8), "little")
        return offset, length

    custom_data_pointer = _pointer()
    audio_pointer       = _pointer()
    cover_pointer       = _pointer()
    marker_defs_pointer = _pointer()
    marker_pointer      = _pointer()

    # --- strings ---
    map_id    = _read_length_prefixed_string(fileBytes).replace(",", "")
    map_name  = _read_length_prefixed_string(fileBytes)
    song_name = _read_length_prefixed_string(fileBytes)

    map_id = "".join("_" if char in SSPM.INVALID_CHARS else char for char in map_id)

    mapper_count = int.from_bytes(fileBytes.read(2), "little")
    mappers = [_read_length_prefixed_string(fileBytes) for _ in range(mapper_count)]

    # --- custom data (seek by pointer rather than trusting sequential position) ---
    custom_data = {}
    if custom_data_pointer[1]:
        try:
            fileBytes.seek(custom_data_pointer[0])
            custom_data = _read_custom_data(fileBytes)
        except Exception as error:
            if _use_strict:
                warn(f"Could not read custom data block: {error}", BytesWarning)
            custom_data = {}

    # --- audio / cover (always seek; sequential reads drift when a block is absent) ---
    audio_bytes = b""
    if contains_audio and audio_pointer[1]:
        fileBytes.seek(audio_pointer[0])
        audio_bytes = fileBytes.read(audio_pointer[1])

    cover_bytes = b""
    if contains_cover and cover_pointer[1]:
        fileBytes.seek(cover_pointer[0])
        cover_bytes = fileBytes.read(cover_pointer[1])

    # --- marker definitions ---
    fileBytes.seek(marker_defs_pointer[0])
    has_notes = False
    definition_count = fileBytes.read(1)[0]

    for index in range(definition_count):
        definition = _read_length_prefixed_string(fileBytes)
        has_notes |= definition == "ssp_note" and index == 0

        fileBytes.read(1)  # number of values, including arrays
        while int.from_bytes(fileBytes.read(1), "little") != TYPE_END:
            pass  # walk the value type list to its terminator

    notes, is_quantum = [], False
    if has_notes:
        fileBytes.seek(marker_pointer[0])
        notes, is_quantum = _read_notes(fileBytes, note_count, skip_marker_type=True)
    elif _use_strict:
        warn("SSPM contains no 'ssp_note' marker definition; no notes were read.", Warning)

    parsed = SSPM(
        note_hash=note_hash,
        difficulty=difficulty,
        export_offset=0,
        last_ms=last_ms,
        song_name=song_name,
        cover_bytes=cover_bytes,
        audio_bytes=audio_bytes,
        map_name=map_name,
        mappers=mappers,
        notes=notes,
        map_id=map_id,
        requires_mod=requires_mod,
        header=header,
        map_rating=map_rating,
        quantum=is_quantum,
        marker_count=marker_count,
        custom_data=custom_data,
        _use_strict=_use_strict,
    )

    # Hydrate the AI tag onto its own attributes, so re-writing a tagged map
    # preserves the tag instead of silently dropping it.
    if custom_data.get(AI_GENERATED_FIELD):
        parsed.ai_generated = True
        parsed.ai_generator = str(custom_data.get(AI_GENERATOR_FIELD, "") or "")
        parsed.ai_fingerprint = str(custom_data.get(AI_FINGERPRINT_FIELD, "") or "")

    return parsed


def _ProcessSSPMV1(fileBytes: BinaryIO, header: Header = None, _use_strict: bool = False) -> SSPM:
    """Parse an SSPM v1 body. The 8-byte header must already be consumed."""

    # --- metadata (newline-terminated strings) ---
    map_id   = _read_newline_terminated_string(fileBytes).replace(",", "")
    map_name = _read_newline_terminated_string(fileBytes)
    mappers  = [
        mapper.strip()
        for mapper in _read_newline_terminated_string(fileBytes).replace(" & ", ", ").split(", ")
        if mapper.strip()
    ]

    last_ms    = int.from_bytes(fileBytes.read(4), "little")
    note_count = int.from_bytes(fileBytes.read(4), "little")
    difficulty = fileBytes.read(1)[0]

    # --- cover: 0x00 none, 0x01 legacy (unused), 0x02 PNG ---
    cover_bytes = b""
    cover_type = int.from_bytes(fileBytes.read(1), "little")
    if cover_type == 0x02:
        cover_bytes = fileBytes.read(int.from_bytes(fileBytes.read(8), "little"))
    elif cover_type not in (0x00, 0x01) and _use_strict:
        warn(f"Unknown v1 cover storage type {hex(cover_type)}", BytesWarning)

    # --- audio: 0x00 none, 0x01 stored file ---
    audio_bytes = b""
    audio_type = int.from_bytes(fileBytes.read(1), "little")
    if audio_type == 0x01:
        audio_bytes = fileBytes.read(int.from_bytes(fileBytes.read(8), "little"))
    elif audio_type != 0x00 and _use_strict:
        warn(f"Unknown v1 audio storage type {hex(audio_type)}", BytesWarning)

    # --- notes (no marker type byte in v1) ---
    notes, is_quantum = _read_notes(fileBytes, note_count, skip_marker_type=False)

    return SSPM(
        difficulty=difficulty,
        export_offset=0,
        last_ms=last_ms,
        song_name=map_name,  # v1 has no separate song name
        cover_bytes=cover_bytes,
        audio_bytes=audio_bytes,
        map_name=map_name,
        mappers=mappers,
        notes=notes,
        map_id=map_id,
        requires_mod=False,
        header=header if header is not None else Header(),
        map_rating=0,
        quantum=is_quantum,
        _use_strict=_use_strict,
    )


def write_sspm(sspm: SSPM, filename: str = None, forcemapid=False, debug: bool = False, **kwargs) -> bytes | None:
    """
    Alternate wrapper function for writing in SSPM.

    Note: It is preferred you use `SSPM.write_sspm(location)` instead.
    """

    for key, value in kwargs.items():
        if hasattr(sspm, key):
            setattr(sspm, key, value)
        else:
            warn(f"{key} is not a valid attribute", Warning)

    if not sspm.notes:
        raise ValueError("Cannot write an SSPM with no notes.")

    header = bytes([
        0x53, 0x53, 0x2b, 0x6d,  # File type signature "SS+M"
        0x02, 0x00,              # SSPM format version
        0x00, 0x00, 0x00, 0x00,  # 4 byte reserved space
    ])

    contains_cover = b"\x01" if sspm.cover_bytes else b"\x00"
    contains_audio = b"\x01" if sspm.audio_bytes else b"\x00"
    requires_mod   = b"\x01" if sspm.requires_mod else b"\x00"

    note_count = np.uint32(len(sspm.notes)).tobytes()
    difficulty = sspm.difficulty.value.to_bytes(1, "little")

    if debug:
        print("Metadata loaded")

    if not sspm.song_name:
        sspm.song_name = "Pysspm2 Default"

    if not forcemapid:
        sspm.map_id = f"{'_'.join(sspm.mappers)}_{sspm.map_name.replace(' ', '_')}"

    # Lengths are byte lengths, not character counts -- non-ASCII names corrupt
    # the file otherwise.
    final_string = (
        _write_length_prefixed_string(sspm.map_id)
        + _write_length_prefixed_string(sspm.map_name)
        + _write_length_prefixed_string(sspm.song_name)
        + len(sspm.mappers).to_bytes(2, "little")
        + b"".join(_write_length_prefixed_string(mapper) for mapper in sspm.mappers)
    )

    if debug:
        print("Strings loaded")

    # --- custom data, including the AI provenance tag ---
    custom_fields: Dict[str, Tuple[int, object]] = {}
    for field_id, value in (sspm.custom_data or {}).items():
        if field_id in (AI_GENERATED_FIELD, AI_GENERATOR_FIELD, AI_FINGERPRINT_FIELD):
            continue  # written from the dedicated attributes below
        custom_fields[field_id] = value if isinstance(value, tuple) else (TYPE_STRING, str(value))

    if sspm.ai_generated:
        custom_fields[AI_GENERATED_FIELD] = (TYPE_INT8, 1)
        custom_fields[AI_GENERATOR_FIELD] = (TYPE_STRING, sspm.ai_generator or "unknown")
        custom_fields[AI_FINGERPRINT_FIELD] = (TYPE_STRING, sspm.compute_ai_fingerprint())

    custom_data = _write_custom_data(custom_fields)

    # --- markers ---
    total_notes = len(sspm.notes)
    markers = bytearray()
    last_ms_value = 0

    for count, (note_x, note_y, note_ms) in enumerate(sspm.notes, start=1):
        if debug and count % 1000 == 0:
            print(f"Notes completed: {count}/{total_notes}", end="\r", flush=True)

        is_grid_aligned = round(note_x) == round(note_x, 2) and round(note_y) == round(note_y, 2)

        ms_bytes = np.uint32(note_ms + sspm.export_offset).tobytes()
        marker_type = b"\x00"
        identifier = b"\x00" if is_grid_aligned else b"\x01"

        if is_grid_aligned:
            x_bytes = np.uint16(round(note_x)).tobytes()[0:1]
            y_bytes = np.uint16(round(note_y)).tobytes()[0:1]
        else:
            x_bytes = np.float32(note_x).tobytes()
            y_bytes = np.float32(note_y).tobytes()

        last_ms_value = max(last_ms_value, int(note_ms))
        markers.extend(ms_bytes + marker_type + identifier + x_bytes + y_bytes)

    last_ms = np.uint32(last_ms_value + sspm.export_offset).tobytes()
    marker_count = np.uint32(total_notes).tobytes()

    if debug:
        print("Markers built")

    map_rating = np.uint16(sspm.map_rating).tobytes()
    metadata = (
        last_ms + note_count + marker_count + difficulty + map_rating
        + contains_audio + contains_cover + requires_mod
    )

    # header + hash[20] + metadata + 10 pointer pairs[8+8] + strings
    offset = len(header) + 20 + len(metadata) + 80 + len(final_string)

    custom_data_offset = np.uint64(offset).tobytes()
    custom_data_length = np.uint64(len(custom_data)).tobytes()
    offset += len(custom_data)

    # Absent blocks get a zeroed pointer AND contribute nothing to the running
    # offset -- advancing here desynchronises every later pointer.
    audio_offset = np.uint64(offset).tobytes() if sspm.audio_bytes else bytes(8)
    audio_length = np.uint64(len(sspm.audio_bytes)).tobytes() if sspm.audio_bytes else bytes(8)
    offset += len(sspm.audio_bytes)

    cover_offset = np.uint64(offset).tobytes() if sspm.cover_bytes else bytes(8)
    cover_length = np.uint64(len(sspm.cover_bytes)).tobytes() if sspm.cover_bytes else bytes(8)
    offset += len(sspm.cover_bytes)

    # one definition, "ssp_note", holding a single position value (0x07)
    marker_definition_bytestring = b"\x01" + _write_length_prefixed_string("ssp_note") + b"\x01\x07\x00"
    marker_definition_offset = np.uint64(offset).tobytes()
    marker_definition_length = np.uint64(len(marker_definition_bytestring)).tobytes()
    offset += len(marker_definition_bytestring)

    marker_offset = np.uint64(offset).tobytes()
    marker_length = np.uint64(len(markers)).tobytes()

    marker_hash = sha1(marker_definition_bytestring + bytes(markers)).digest()
    sspm.note_hash = marker_hash

    pointers = (
        custom_data_offset + custom_data_length
        + audio_offset + audio_length
        + cover_offset + cover_length
        + marker_definition_offset + marker_definition_length
        + marker_offset + marker_length
    )

    sspm_bytes = (
        header + marker_hash + metadata + pointers + final_string
        + custom_data + sspm.audio_bytes + sspm.cover_bytes
        + marker_definition_bytestring + bytes(markers)
    )

    if debug:
        print(f"Wrote {len(sspm_bytes)} bytes ({total_notes} notes)")

    if filename:
        with open(filename, "wb") as file:
            file.write(sspm_bytes)
        return None

    return sspm_bytes
