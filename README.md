# pysspm-rhythia

The official python library dedicated to reading, writing, and modifying the SSPM file format from the video game "Rhythia".

> ***Note: This is V2 of `PYSSPM`. This version is a complete rewrite of the original V1, with more "support" and type hinting***

## SSPM libray information

The main library includes these features:

> 1. Reading .SSPM files
> 2. Modifying SSPM data
> 3. Writing .SSPM files

Extras:

> 1. Difficulty Calculation (Not implemented in V2.0)
> 2. Note Classification (Not implmented in V2.0)

## How to install/use

To install the library, run:

```bash
pip install pysspm-rhythia
```

> Requires Python 3.10 or newer.

to start using the library, create a python script and load up pysspm.

```python
from pysspm_rhythia import read_sspm


# Example of loading a SSPMfile
sspm = read_sspm("*.sspm")

# Example of turning it into a roblox sound space file

with open("output.txt", "w") as f:
    f.write(sspm.NOTES2TEXT())

```

> *Functionality does not end there. When reading files, you have full access to all the metadata, and other information stored in the variables.*

**Some common variables you will find are:**

1. `cover_bytes` the byteform of the image if cover was found
2. `audio_bytes` the byteform of the audio in `.mp3` form if audio was found
3. `header`: {"Signature": ..., "Version": ...}
4. `hash`: a SHA-1 hash of the markers (notes) in the map
5. `map_id`: A unique combination using the mappers and map name*
6. `mappers`: a list containing each mapper.
7. `map_name`: The name given to the map.
8. `song_name`: The original name of the audio before imported. Usually left as artist name - song name
9. `custom_data`: a dictionary of the custom data fields found in the file.
10. `quantum`: Determins if the level contains ANY float value notes.
11. `notes`: A list of tuples containing all notes. | Example of what it Notes is: `[(x, y, ms), (x, y, ms), (x, y, ms) . . .]`

```python
from pysspm_rhythia import read_sspm, write_sspm

# Example of loading a SSPMfile
sspm = read_sspm("*.sspm")

# changing the decal to be a different image
with open("cover.png", 'rb') as f:
    sspm.cover_bytes = f.read() # reading the BYTES of the image

print(sspm.has_cover(), sspm.has_audio()) # -> True True

# Finally save the sspm file with the newly configured settings
sspm.write('sspmFile.sspm')

# alternatively:
write_sspm(sspm, 'sspmFile.sspm') # takes a pre-configured sspm object

```

you can modify metadata information within sspm with ease

```py
from pysspm_rhythia import read_sspm, write_sspm

sspm = read_sspm("*.sspm")

sspm.mappers.extend('DigitalDemon') # adding another mapper to the mapper list
sspm.write('SSPMFile.sspm')

```

## SSPM v1

`read_sspm()` detects the format version from the header and reads both v1 and v2.
Writing always produces v2, so reading a v1 map and writing it back up-converts it:

```python
from pysspm_rhythia import read_sspm

legacy = read_sspm("old_map.sspm")   # v1
print(legacy.header.version)          # -> 1

legacy.write("modern_map.sspm")       # written as v2
```

Note that v1 has no separate song name and no map rating, so `song_name` mirrors
`map_name` and `map_rating` is `0`.

## Tagging AI-generated maps

Maps produced by a generator can carry a provenance tag, so tooling downstream can
tell machine-generated charts from hand-made ones and spot re-uploads of the same
generated chart.

```python
from pysspm_rhythia import SSPM

sspm = SSPM(
    map_name="Artist - Song",
    difficulty="hard",
    mappers=["my-generator"],
    notes=[(1, 1, 500), (0, 1, 250)],
)

sspm.mark_ai_generated("my-generator/1.0")   # tool or model identifier
sspm.write("generated.sspm")
```

Reading it back:

```python
sspm = read_sspm("generated.sspm")

sspm.ai_generated     # -> True
sspm.ai_generator     # -> "my-generator/1.0"
sspm.ai_fingerprint   # -> "2f30038b4e89..."
```

**How it works.** The tag is stored in the v2 *custom data* block as three fields:

| Field            | Type          | Meaning                                     |
| ---------------- | ------------- | ------------------------------------------- |
| `ai_generated`   | `0x01` int8   | `1` when the map was machine-generated       |
| `ai_generator`   | `0x09` string | Identifier of the tool/model that made it    |
| `ai_fingerprint` | `0x09` string | SHA-1 over the note stream and generator ID  |

The v2 spec has readers skip custom data fields they don't recognise, so tagged
maps stay playable in Rhythia, SS+ and SSQE.

The fingerprint is derived from **the notes and the generator only** — not the
title, cover or audio. Retitling a generated map or swapping its song leaves the
fingerprint unchanged, while editing the chart changes it. That makes the same
generated chart recognisable across re-uploads.

The tag survives a read/modify/write cycle: reading a tagged map restores the
`ai_*` attributes, so re-writing it keeps the tag rather than silently dropping it.

> The tag is an honest-provenance marker for cooperating tools, not an
> anti-cheat measure — anyone can strip the custom data block.

## Custom data

Any custom data fields present in a v2 file are parsed into `sspm.custom_data` as a
plain dict, and can be written back by assigning `{field_id: (type_id, value)}`:

```python
from pysspm_rhythia.parser import TYPE_STRING, TYPE_UINT32

sspm.custom_data["my_tool_notes"] = (TYPE_STRING, "generated at 120bpm")
sspm.custom_data["my_tool_seed"]  = (TYPE_UINT32, 42)
sspm.write("out.sspm")
```

## Function Documentation

A in-depth list of things you can do with this library

WIP FOR V2

## Roadmap (May get completed)

TODO LIST FOR V2: (In order of priority)

- Refactor codebase (~40% done) ⛔
- Add typing support for library ✅
- add proper documentation on github ✅
- add proper documentation in code ✅
- add loading of sspmV2  ✅
- add support for creating sspmV2 ✅
- add support for sspmv1 loading ✅
- add custom block support in loading ✅
- Tag AI-generated maps ✅
- Drop numpy dependency
- Implement Extras difficulty calculation (Obsiids method, rhythia-online starCalculation)
- Support for Pheonix/Nova Filetype (When I get my hands on the data structure)
- Writing SSPM v1 (reading is supported; writing always emits v2)

Made with 💖 by DigitalDemon (David Jed)

> Documentation last updated: `2026-08-21` | `V2.1.0`
