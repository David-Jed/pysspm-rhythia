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
pip install pysspm-rythia
```

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
9. `custom_values`: NOT IMPLEMENTED | will return a dictionary of found custom blocks.
10. `quantum`: Determins if the level contains ANY float value notes.
11. `notes`: A list of tuples containing all notes. | Example of what it Notes is: `[(x, y, ms), (x, y, ms), (x, y, ms) . . .]`

```python
from pysspm_rhythia import read_sspm, write_sspm

# Example of loading a SSPMfile
sspm = read_sspm("*.sspm")

# changing the decal to be a different image
if sspm.has_cover():
    sspm.add_cover() # takes location OR bytes

    with open("cover.png", 'rb') as f: # alternate method
        sspm.cover_bytes = f.read() # reading the BYTES of the image

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

## Advanced guide (W.I.P)

This shows the more advanced things you can do by giving examples of custom written code.

```python

# Not implemented yet...
# Support for custom blocks and AI tagging coming soon..

```

*More advanced documentation will be added in the near future...*

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
- add support for sspmv1 loading 🔴 (Use Pre-V2.0.0 release to use this for now)
- add custom block support in loading
- Drop numpy dependency
- Implement Extras difficulty calculation (Obsiids method, rhythia-online starCalculation)
- Support for Pheonix/Nova Filetype (When I get my hands on the data structure)

Made with 💖 by DigitalDemon (David Jed)

> Documentation last updated: `2025-07-22` | `V2.0.0`
