from dataclasses import dataclass, field
from enum import Enum
from io import BytesIO
from hashlib import sha1
from types import NoneType
from typing import BinaryIO, Annotated, List, Literal, Tuple, Dict, Union
import numpy as np
from warnings import warn


# BIG CHANGE: REFACTORED CODEBASE

class Difficulty(Enum):
    """
    ### Class handling all difficulty parameters withing SSPM filetypes

    - na = 0
    - easy = 1
    - medium = 2
    - hard = 3
    - logic = 4
    - tasukete = 5
    - brrrrr = 5

    > Note: brrrrr filetype is the same as tasukete, just used within roblox sound space <br>
    """
    na      = 0x00
    easy    = 0x01
    medium  = 0x02
    hard    = 0x03
    logic   = 0x04
    tasukete= 0x05
    brrrrr   = 0x05

    def __str__(self):
        return self.name

@dataclass
class Header:
    """
    # SSPM File Header
    contains:
    - signature | SS+M | 4 bytes 
    - version | 2, or 1 | 2 bytes
    - reserve | 0x00 | 4 bytes
    """
    signature = bytes([0x53, 0x53, 0x2b, 0x6d])
    version = 2 #bytes([0x02, 0x00])
    reserve = bytes([0x00, 0x00, 0x00, 0x00])

class Custom_data:
    """
    # NOT IMPLEMENTED YET

    handles all custom data parameters within SSPM objects.
    """
    pass
    #raise NotImplementedError("class not implemented yet.")

@dataclass
class SSPM:
    """
    # SSPM
    Class that contains all parsed logic witihin sspm v1, v2 filetypes

    ```
    # basic use case
    sspm = SSPM(
        map_name='author name - song name',
        difficulty='na',
        mappers=["DigitalDemon", "Fog"],
        notes=[(1.5, 1.2, 500), (1, 2, 1262), (2, 0, 1423)]
        )
    
    ```

    - `map_name:` (Required) name of the SSPM map | Standard is `author name - song name`
    - `difficulty:` (Required) registered level difficulty. use difficulty.value to get intiger
    - `mappers:` (Required) list of mappers who contributed/created SSPM level
    - `notes:` (Required) list of notes to be played in SSPM.
    - `note_hash:` calculated on write
    - `song_name:` name of mp3/ogg song unless modified
    - `cover_bytes:` raw bytes of png image, does not support apng format. (Read SSPMV2 documentation)
    - `audio_bytes:` raw bytes of mp3/ogg audio.
    - `map_id:` Calculated on write() | unique identifier used in rhythia for your map | can be overwritten (not recommended)
    - `map_rating:` ? rating system within game ? | (Please reach out to me if you know what this actually does within rhythia)
    - `quantum:` Calculated on write() | determines if level contains "float value" notes.
    - `requires_mod:` ? if map requires any mods ? | (Please reach out to me if you know what this actually does within rhythia)
    - `header:` Calculated on runtime. handles signature, version and reserve bytes
    - `_use_strict:` Enforces stricter handling of IO. use only if map is rendered corrupt by rhythia. | last resort
    - `metadata:` W.I.P | Does not do anything

    > Note: for any extra information, read V2 documentation: https://github.com/basils-garden/types/blob/main/sspm/v2.md#data-type-values 
    """
    INVALID_CHARS = {'/', '\\', ':', '*', '?', '"', '<', '>', '|'}


    difficulty: Union[Difficulty, Literal["na", "easy", "medium", "hard", "logic", "tasukete", "brrrrr"], int]
    map_name: str
    mappers: List[str]
    notes: List[Tuple[int | float, int | float, int]]


    export_offset: int  = 0
    last_ms: int        = 0
    song_name: str      = '' # set to map_name if defaulted
    map_rating: int     = 0
    quantum: bool       = False
    map_id: str         = ''
    cover_bytes: bytes  = b''
    audio_bytes: bytes  = b''
    requires_mod: bool  = False
    header: bytes       = field(default_factory=lambda: Header)  # make this safe
    metadata: Dict      = field(default_factory=dict)           # avoids mutable default
    note_hash: Annotated[bytes, 20] = b""

    marker_count: int   = 0
    custom_data: Dict   = field(default_factory=dict)

    # AI provenance. Written into the v2 custom data block on write(); readers
    # that don't know these fields skip them, so tagged maps stay playable.
    # This will be useful in up-coming projects.
    ai_generated: bool   = False
    ai_generator: str    = ''
    ai_fingerprint: str  = ''

    _use_strict: bool   = False

    def __post_init__(self):
        if len(self.note_hash) > 20:
            raise ValueError("note_hash must be SHA-1 HASH at exactly 20 bytes")

        if not isinstance(self.difficulty, Difficulty):
            if isinstance(self.difficulty, str):
                self.difficulty = Difficulty[self.difficulty]
            elif isinstance(self.difficulty, int):
                self.difficulty = Difficulty(self.difficulty)
            else:
                raise ValueError(f"Invalid difficulty: {self.difficulty}")

        if self.song_name == '':
            self.song_name = self.map_name

    def write(self, filename: str = None, **kwargs) -> bytes | None:
        """
        Creates a SSPM v2 file based on variables passed in, or already set. <br>
        If no filepath is passed in, it will return file as bytes
        <br>
        Variables that need to be covered:
        1. `coverBytes`: Cover image in bytes form, or None
        2. `audioBytes`: Audio in bytes form, or None
        3. `Difficulty`: one of Difficulties dictionary options, or 0x00 - 05 OR "N/A", "Easy", "Medium", "Hard", "Logic", "Tasukete"
        4. `mapName`: The name of the map. Rhythia guidelines suggests `artist name - song name`
        5. `mappers`: a list of strings containing the mapper(s)
        6. `notes`: a list of tuples as shown below
        7. `forcemapid`: if enabled, overwrite mapId to be added instead | otherwise defaults to mappers + map name | make sure its only ASCII characters
        ```python
        # (x, y, ms)
        self.notes = [
            (1, 2, 1685), # X, Y, MS
            (1.22521, 0.156781, 2000)
        ]#...
        ```
        <br>
        `**kwargs`: pass in any of the variables shown above.
        
        Example usage:

        ```python
        from sspmLib import SSPMParser
        
        sspm = SSPMParser()
        sspm.ReadSSPM(file_path) # reads
        sspm.Difficulty = 5 # changes difficulty to Tasukete
        
        with open(output_path+".sspm", "wb") as f:
            f.write(sspm.WriteSSPM())
        ```
        """
        from pysspm_rhythia.parser import write_sspm
        return write_sspm(self, filename=filename, **kwargs)

    def write_sspm(self, filename: str = None, **kwargs) -> bytes | None:
        """Wrapper class for SSPM.write() | Functions the same"""
        return self.write(filename=filename, **kwargs)

    def NOTES2TEXT(self) -> str:
        """
        Converts Notes to the standard sound space text file form. Commonly used in Roblox sound space
        """
        textString = ''
        for x, y, ms in self.notes:
            if textString == '':
                textString+=f",{x}|{y}|{ms}"
            else:
                textString+=f",{x}|{y}|{ms}"
            
        return textString

    def has_cover(self) -> bool:
        return True if self.cover_bytes else False

    def has_audio(self) -> bool:
        return True if self.audio_bytes else False

    # Ai assisted code.
    def compute_ai_fingerprint(self) -> str: 
        """
        Deterministic SHA-1 over the note stream plus the generator ID.

        Two maps with identical notes and generator produce identical
        fingerprints, so duplicates and re-uploads of a generated map stay
        detectable even if the title, cover or audio are swapped out.
        """
        digest = sha1()
        digest.update((self.ai_generator or "unknown").encode("utf-8"))
        for note_x, note_y, note_ms in sorted(self.notes, key=lambda note: note[2]):
            digest.update(f"{float(note_x):.4f},{float(note_y):.4f},{int(note_ms)};".encode("ascii"))
        return digest.hexdigest()

    def mark_ai_generated(self, generator: str) -> "SSPM":
        """
        Tag this map as machine-generated by `generator` (e.g. `"my-tool/1.2"`).

        The tag is written into the v2 custom data block on `write()`. Readers
        that don't recognise the fields skip them, so the map stays playable.
        """
        if not generator:
            raise ValueError("generator must be a non-empty identifier, e.g. 'my-tool/1.2'")

        self.ai_generated = True
        self.ai_generator = generator
        self.ai_fingerprint = self.compute_ai_fingerprint()
        return self
    # End ai assisted code.
        
def read_sspm(file: str | BinaryIO, debug: bool = False, _use_strict: bool = False):
    """
    Reads and processes any SSPM file. <br>
    `File:` Takes in directory of sspm, or BinaryIO object stored in memory.
    `debug:` Useful for getting readable outputs of steps taken.
    `_use_strict:` enforces strict handling. use only if map corrupts when loading in other programs..

    
    SSPM (Sound space plus map file) version 1 read is now supported (T.Y fog), however legacy v1 file write out is not.
    <br><br>
    

    ### Returns:
    1. `coverBytes` if cover was found
    2. `audioBytes` if audio was found
    3. `Header`: {"Signature": ..., "Version": ...}
    4. `Hash`: a SHA-1 hash of the markers in the map
    5. `mapID`: A unique combination using the mappers and map name*. 
    6. `mappers`: a list containing each mapper.
    7. `mapName`: The name given to the map.
    8. `songName`: The original name of the audio before imported. Usually left as artist name - song name
    9. `customValues`: NOT IMPLEMENTED | will return a dictionary of found custom blocks.
    10. `isQuantum`: Determins if the level contains ANY float value notes.
    11. `Notes`: A list of tuples containing all notes. | 
    Example of what it Notes is: `[(x, y, ms), (x, y, ms), (x, y, ms) . . .]`

    ```
    import pysspm_rhythia as pysspm

    sspm_file = pysspm.ReadSSPM("0a0cd80b7c2ef2672d603f225ee9a372f75698ec.sspm") # SSPM object
    # you can handle SSPM however you want
    ```
    <br><br>
    > ***Returns `SSPM` object***
    """

    coverBytes = None
    audioBytes = None

    if isinstance(file, str): # If its a directory we convert it.
        with open(file, "rb") as f:
            file_bytes = BytesIO(f.read())
    else:
        file_bytes = file

    # handle the header files
    header = Header()
    header.signature = file_bytes.read(4)
    header.version = int.from_bytes(file_bytes.read(2), 'little')  # 16 bit uint
    # v2 reserves 4 bytes, v1 reserves 2
    header.reserve = file_bytes.read(4) if header.version == 2 else file_bytes.read(2)

    # File check to make sure everything in the header is A-OK
    if debug:
        print("SSPM Version: ", header.version)

    if header.signature != b"\x53\x53\x2b\x6d": # SS+M as bytes
        raise TypeError("SS+M signature type was not found. What was found instead:", header.signature)
    
    match header.version: # cleaner implementation
        case 2:
            from pysspm_rhythia.parser import _ProcessSSPMV2
            return _ProcessSSPMV2(file_bytes, header, _use_strict)
        case 1:
            from pysspm_rhythia.parser import _ProcessSSPMV1
            return _ProcessSSPMV1(file_bytes, header, _use_strict)
        case _:
            raise ValueError("SSPM version does not match known versions. Versions (1, 2) FOUND:", header.version)


# Deprecated codebase. Keep in case

class SSPMParser:
    """
    # DEPRECATED CODE

    ### reads and converts Sound space plus maps into many other readable forms.

    for anyone interested in the "Amazing" documentation from the creator: <link>https://github.com/basils-garden/types/blob/main/sspm/v2.md</link>...
    <br>
    More to come soon...
    """

    INVALID_CHARS = {'/', '\\', ':', '*', '?', '"', '<', '>', '|'}
    HEADER_SIGNATURE = b'SS+m'
    DEFAULT_VERSION = b'\x02\x00'
    RESERVED_SPACE_V2 = b'\x00\x00\x00\x00'
    
    DIFFICULTIES = { 
        "N/A": 0x00,
        "Easy": 0x01,
        "Medium": 0x02,
        "Hard": 0x03,
        "Logic": 0x04,
        "Tasukete": 0x05,
    }

    def __init__(self):
        # Warn on use, not on import
        warn("this class has been deprecated in V2. Please use SSPM() directly, or read_sspm() instead.", DeprecationWarning, stacklevel=2)

        self.export_offset = 0
        self.Header = bytes([ # base header
            0x53, 0x53, 0x2b, 0x6d, # File type signature "SS+M"
            0x02, 0x00, # SSPM format version (0x02 or 0x01) 2 by default
            0x00, 0x00, 0x00, 0x00, # 4 byte reserved space.
        ])
        self.last_ms = None
        self.last_ms = None
        self.metadata = {}
        self.song_name = None
        self.requiresMod = 0
        self.strict = False
        self.coverBytes = None
        self.difficulty = 0
        self.audioBytes = None
        self.map_name = None
        self.mappers = None
        self.Notes = None
        self.map_id = None
        self.custom_data_offset = 0

    def _GetNextVariableString(self, data: BinaryIO, fourbytes: bool = False, encoding: str = "ASCII", V2: bool = True) -> str: # Why did this have a self variable??
        # Read 2 bytes for length (assuming little-endian format)
        length_bytes = data.read(2 if V2 else 1)
        
        # Convert the length bytes to an integer | Bugfix reading improper data
        length_f = np.int32(int.from_bytes(length_bytes, byteorder='little')) if fourbytes else np.int16(int.from_bytes(length_bytes, byteorder='little'))
        
        # Read the string of the determined length
        finalString = data.read(length_f)
        try: # game changed encoding to support BOTH ASCII & UTF-8
            fsd = finalString.decode(encoding=encoding)
        except:
            fsd = finalString.decode(encoding='utf-8')
        
        return fsd
    
    def _NewLineTerminatedString(self, data: BinaryIO, encoding: str = "ASCII") -> str: # for SSPMv1

        final_string = bytearray()
        while True:
            stringbyte = data.read(1) # keep going by one bit
            if stringbyte == b'\n': # once it reaches a new line, break
                break
            final_string.extend(stringbyte)
        
        try: # game changed encoding to support BOTH ASCII & UTF-8 for wider language support
            fsd = final_string.decode(encoding=encoding)
        except:
            fsd = final_string.decode(encoding='utf-8')
        
        return fsd

    
    def WriteSSPM(self, filename: str = None, forcemapid=False, debug: bool = False, **kwargs) -> bytearray | NoneType:
        """
        Creates a SSPM v2 file based on variables passed in, or already set. <br>
        If no filepath is passed in, it will return file as bytes
        <br>
        Variables that need to be covered:
        1. `coverBytes`: Cover image in bytes form, or None
        2. `audioBytes`: Audio in bytes form, or None
        3. `Difficulty`: one of Difficulties dictionary options, or 0x00 - 05 OR "N/A", "Easy", "Medium", "Hard", "Logic", "Tasukete"
        4. `mapName`: The name of the map. Rhythia guidelines suggests `artist name - song name`
        5. `mappers`: a list of strings containing the mapper(s)
        6. `notes`: a list of tuples as shown below
        7. `forcemapid`: if enabled, overwrite mapId to be added instead | otherwise defaults to mappers + map name | make sure its only ASCII characters
        ```python
        # (x, y, ms)
        self.notes = [
         (1, 2, 1685), # X, Y, MS
         (1.22521, 0.156781, 2000)
        ]#...
        ```
        <br>
        `**kwargs`: pass in any of the variables shown above.
        
        Example usage:

        ```python
        from sspmLib import SSPMParser
        
        sspm = SSPMParser()
        sspm.ReadSSPM(file_path) # reads
        sspm.Difficulty = 5 # changes difficulty to Tasukete
        
        with open(output_path+".sspm", "wb") as f:
            f.write(sspm.WriteSSPM())
        ```
        """
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                warn(f"{key} is not a valid attribute", Warning)


        self.Header = bytes([ # base header
            0x53, 0x53, 0x2b, 0x6d, # File type signature "SS+M"
            0x02, 0x00, # SSPM format version (0x02 or 0x01) Set to 2 by default
            0x00, 0x00, 0x00, 0x00, # 4 byte reserved space.
        ])

        # configs
        self.contains_cover = b"\x01" if self.coverBytes != None else b"\x00" # 0 or 1
        self.contains_audio = b"\x01" if self.audioBytes != None else b"\x00" # 0 or 1
        self.requiresMod = b"\x01" if self.requiresMod == 1 or self.requiresMod == b"\x01" else b"\x00" # Who actually uses this though?
        
        #print(self.Notes[-1][2])
        self.last_ms = np.uint32(self.Notes[-1][2]).tobytes()  # np.uint32 object thus far | 4 bytes | base before getting proper one
        self.noteCount = np.uint32(len(self.Notes)).tobytes() # bytes should be length of 4
        self.markerCount = self.noteCount # nothing changed from last time

        self.difficulty = self.difficulty if self.DIFFICULTIES.get(self.difficulty) == None else self.DIFFICULTIES.get(self.difficulty)
        self.difficulty = self.difficulty.to_bytes(1, 'little') if isinstance(self.difficulty, int) else self.difficulty

        if debug:
            print("Metadata loaded")

        # good until here
        #self.map_id = 
        self.song_name = "sspmLib Song - author".encode("ASCII") if not self.song_name else self.song_name.encode("ASCII")

        if not forcemapid:
            self.map_id = f"{'_'.join(self.mappers)}_{self.map_name.replace(' ', '_')}".encode("ASCII") # combines mappers and map name to get the id.
        else:
            self.map_id = self.map_id.encode("ASCII")
            
        self.map_idf = len(self.map_id).to_bytes(2, 'little')
        self.map_name = self.map_name.encode("ASCII")
        self.map_nameF = len(self.map_name).to_bytes(2, 'little')
        self.song_nameF = len(self.song_name).to_bytes(2, 'little')

        self.mapper_countf = len(self.mappers).to_bytes(2, 'little')
        #self.mappersf = '\n'.join(self.mappers).encode('ASCII') # Possible bug | maybe include breakchar like \n
        mappers_f = bytearray()

        # Iterate through each mapper in the mappers list
        for mapper in self.mappers:
            # Encode the mapper string to ASCII bytes
            mapper_f = mapper.encode('ASCII')
            
            # Get the length of the mapper string as a 2-byte little-endian value
            mapper_length = len(mapper_f).to_bytes(2, 'little')
            
            # Concatenate the length and the actual mapper string
            mapper_final = mapper_length + mapper_f
            
            # Append to the mappersf byte array
            mappers_f.extend(mapper_final)

        # Store the result in the instance variable
        self.mappers_f = bytes(mappers_f)

        self.strings = self.map_idf+self.map_id+self.map_nameF+self.map_name+self.song_nameF+self.song_name+self.mapper_countf+self.mappersf # merge values into a string because we are done with this section
        if debug:
            print("Strings loaded")

        self.custom_data = b"\x00\x00" # 2 bytes, no custom data supported right neoww
        self.custom_data = b"\x00\x00" # 2 bytes, no custom data supported right neoww

        # FEATURE REQUEST: Add support for custom difficulty here.

        # Pointer locations in byte array

        
        if debug:
            print("1/2 pointers loaded. Note creation next")

        self.Markers = b''

        count = 0
        totalNotes = len(self.Notes)
        
        markers = bytearray()
        last_ms = 0
        
        for nx, ny, nms in self.Notes:
            count += 1
            
            if debug and count % 1000 == 0:
                print(f"Notes completed: {count}/{totalNotes}", end="\r", flush=True)
            
            rounded_nx = round(nx)
            rounded_ny = round(ny)
            rounded_nx_2 = round(nx, 2)
            rounded_ny_2 = round(ny, 2)
            
            # Calculate the bytes
            ms_bytes = np.uint32(nms + self.export_offset).tobytes()
            marker_type = b'\x00'
            identifier = b'\x00' if (rounded_nx == rounded_nx_2 and rounded_ny == rounded_ny_2) else b'\x01'
            
            if identifier == b'\x00':
                x_bytes = np.uint16(rounded_nx).tobytes()[0:1]
                y_bytes = np.uint16(rounded_ny).tobytes()[0:1]
            else:
                x_bytes = np.float32(nx).tobytes()
                y_bytes = np.float32(ny).tobytes()
            if last_ms < nms:
                last_ms = nms
            
            final_marker = ms_bytes + marker_type + identifier + x_bytes + y_bytes
            markers.extend(final_marker)
        
        self.last_ms = np.uint32(last_ms).tobytes() # because list is not in order.

        if debug:
            print("All pointers finished")


        # adding everything together
        metadata = self.last_ms + self.noteCount + self.markerCount + self.difficulty + b"\x00\x00" + self.contains_audio + self.contains_cover + self.requiresMod # level rating Not fully implemented yet 
        offset = len(self.Header) + 20 + len(metadata) + 80 + len(self.strings)
        # pointers
        self.custom_data_offset = np.uint64(offset).tobytes()
        self.custom_dataLength = np.uint64(len(self.custom_data)).tobytes()
        offset+= len(self.custom_data)

        # bugfix: Misread documentation
        self.audioOffset = np.uint64(offset).tobytes()
        self.audioLength = np.uint64(len(self.audioBytes)).tobytes() if self.contains_audio == b'\x01' else b''#b'\x00\x00\x00\x00\x00\x00\x00\x00' # 8 bytes filler if no audio length found | Possible bug if no audio found, and reading special block fails. | may default to start of file.
        offset+= len(self.audioBytes) if self.contains_audio == b'\x01' else 0 # len(b'\x00\x00\x00\x00\x00\x00\x00\x00') # 8
        self.audioBytes = b'' if self.audioBytes == None else self.audioBytes

        self.coverOffset = np.uint64(offset).tobytes()
        self.coverLength = np.uint64(len(self.coverBytes)).tobytes() if self.contains_cover == b'\x01' else b''#b'\x00\x00\x00\x00\x00\x00\x00\x00' # 8 bytes filler if no audio length found 
        offset+= len(self.coverBytes) if self.contains_cover == b'\x01' else 0#len(b'\x00\x00\x00\x00\x00\x00\x00\x00') # 8
        self.coverBytes = b'' if self.coverBytes == None else self.coverBytes

        self.note_definition = "ssp_note".encode("ASCII")
        self.note_definition_f = len(self.note_definition).to_bytes(2, 'little') + self.note_definition
        self.marker_def_start = b"\x01"
        self.marker_def_end = b"\x01\x07\x00" # var markerDefEnd = new byte[] { 0x01, /* one value */ 0x07, /* data type 07 - note */ 0x00 /* end of definition */ };

        self.marker_definitions = self.marker_def_start+self.note_definition_f+self.marker_def_end
        self.marker_definitions_offset = np.uint64(offset).tobytes()
        self.marker_definitions_length = np.uint64(len(self.marker_definitions)).tobytes()
        offset+=len(self.marker_definitions)

        # notes n stuff
        self.Markers = markers
        self.marker_offset = np.uint64(offset).tobytes()
        self.marker_length = np.uint64(len(self.Markers)).tobytes()

        # hashing
        self.marker_set = self.marker_definitions+self.Markers
        s_hash = sha1(self.marker_set).digest()

        pointers = b''
        pointers+=self.custom_data_offset+self.custom_dataLength+self.audioOffset+self.audioLength+self.coverOffset+self.coverLength+self.markerDefinitionsOffset+self.markerDefinitionsLength+self.markerOffset+self.markerLength

        if debug:
            print(self.last_ms)
            print(self.last_ms)
            print(metadata)
            print(pointers)
            print(self.strings)
            print(self.custom_data)
            print(self.audioBytes[0:10])
            print(self.coverBytes[0:10])

        self.SSPMData = self.Header+s_hash+metadata+pointers+self.strings+self.custom_data+self.audioBytes+self.coverBytes+self.markerDefinitions+self.Markers
        
        if filename:
            with open(filename, 'wb') as f:
                f.write(self.SSPMData)
            return None
        
        return self.SSPMData
        

        raise NotImplementedError("Writing SSPM files at this time is being actively worked on. This currently does not function yet") # Old

    def ReadSSPM(self, file: str | BinaryIO, debug: bool = False):
        """
        Reads and processes any SSPM file. <br>
        `File:` Takes in directory of sspm, or BinaryIO object stored in memory.
        `debug:` Useful for getting readable outputs of steps taken.
        ## Warning
        SSPM (Sound space plus map file) version 1 is not supported at this time. loading this file may raise errors
        <br><br>
        

        ### Returns:
        1. `coverBytes` if cover was found
        2. `audioBytes` if audio was found
        3. `Header`: {"Signature": ..., "Version": ...}
        4. `Hash`: a SHA-1 hash of the markers in the map
        5. `mapID`: A unique combination using the mappers and map name*. 
        6. `mappers`: a list containing each mapper.
        7. `mapName`: The name given to the map.
        8. `songName`: The original name of the audio before imported. Usually left as artist name - song name
        9. `customValues`: NOT IMPLEMENTED | will return a dictionary of found custom blocks.
        10. `isQuantum`: Determins if the level contains ANY float value notes.
        11. `Notes`: A list of tuples containing all notes. | 
        Example of what it Notes is: `[(x, y, ms), (x, y, ms), (x, y, ms) . . .]`
        
        <br><br> ***Returns itself***

        """

        self.cover_bytes = None
        self.audio_bytes = None

        if isinstance(file, str): # If its a directory we convert it.
            with open(file, "rb") as f:
                file_bytes = BytesIO(f.read())
        else:
            file_bytes = file
                
        self.Header = { # all ascii
            "Signature": file_bytes.read(4),
            "Version": 2 if file_bytes.read(2) == b'\x02\x00' else 1, # checking version of SSPM file
        }
        self.Header["Reserve"] = file_bytes.read(4) if self.Header.get("Version") == 2 else file_bytes.read(2), # reserve (0x00 00 00 00) in v2, otherwise (0x00 00)


        # File check to make sure everything in the header is A-OK
        if debug:
            print("SSPM Version: ", self.Header.get("Version"))

        if self.Header.get("Signature") != b"\x53\x53\x2b\x6d":
            raise ValueError("SS+M signature was not found. What was found instead:", self.Header.get("Signature"))
        if self.Header.get("Version") == 2:
            self._ProcessSSPMV2(file_bytes)
        elif self.Header.get("Version") == 1:
            self._ProcessSSPMV1(file_bytes)
        else:
            raise ValueError("SSPM version does not match known versions. Versions (1, 2) FOUND:", self.Header.get("Version"))


        return self
    
    def _ProcessSSPMV2(self, file_bytes: BinaryIO):
        
        # static metadata

        self.Hash = file_bytes.read(20)
        self.last_ms = int.from_bytes(file_bytes.read(4), 'little') # 32bit uint
        self.noteCount = file_bytes.read(4) # 32bit uint
        self.markerCount = file_bytes.read(4) # No clue what this is, ill figure it out | 32bit uint
        
        self.difficulty = file_bytes.read(1) # 0x00 01 02 03 04 05
        self.mapRating = file_bytes.read(2) # 16bit uint
        self.contains_audio = file_bytes.read(1) # 0x00 01?
        self.contains_cover = file_bytes.read(1) # 0x00 01?
        self.requiresMod = file_bytes.read(1) # 0x00 01?

        # pointers | If not present then is left as 8 bytes of 0
        self.custom_data_offset = file_bytes.read(8)
        self.custom_dataLength = file_bytes.read(8)
        self.audioOffset = file_bytes.read(8) if self.contains_audio[0] == 1 else None
        self.audioLength = file_bytes.read(8) if self.contains_audio[0] == 1 else None
        self.coverOffset = file_bytes.read(8) if self.contains_cover[0] == 1 else None
        self.coverLength = file_bytes.read(8) if self.contains_cover[0] == 1 else None
        self.markerDefinitionsOffset = file_bytes.read(8)
        self.markerDefinitionsLength = file_bytes.read(8)
        self.markerOffset = file_bytes.read(8)
        self.markerLength = file_bytes.read(8)

        # VariableLength Items..
        self.map_id = self._GetNextVariableString(file_bytes).replace(",", "")
        self.map_name = self._GetNextVariableString(file_bytes)
        self.song_name = self._GetNextVariableString(file_bytes)

        for i in range(len(self.map_id)): # getting mapID
            if self.map_id[i] in self.INVALID_CHARS: # Create invalidChars thing
                self.map_id = self.map_id[:i] + '_' + self.map_id[i+1:]
        
        mapperCount = file_bytes.read(2)
        self.mapper_countFloat = int.from_bytes(mapperCount, byteorder="little") #np.uint16(mapperCount)
        self.mappers = [] # for now
        
        for i in range(self.mapper_countFloat): # Can have multiple mappers in a file.
            
            if True:
            #try: # temporary solution until I figure out whats happening
                self.mappers.append(self._GetNextVariableString(file_bytes))
            #except:
            #    pass
        try:
            # Oh god Custom data.... | Only supports custom difficulty thus far
            customData = file_bytes.read(2) # ??
            self.custom_dataTotalLength = np.uint16(customData)
            
            for i in range(self.custom_dataTotalLength):
                field = self._GetNextVariableString(file_bytes)
                id = file_bytes.read(1)
                if id[0] == "\x00": # no 0x08 and 0x0a according to SSQE...
                    continue
                elif id[0] == "\x01":
                    file_bytes.read(1) # skipping
                elif id[0] == "\x02":
                    file_bytes.read(2) # skipping
                elif id[0] == "\x03":
                    pass
                elif id[0] == "\x04":
                    pass
                elif id[0] == "\x05":
                    file_bytes.read(4) # skipping
                elif id[0] == "\x06":
                    file_bytes.read(8) # skipping
                elif id[0] == "\x07":
                    case_type = file_bytes.read(1)
                    if case_type == "\x00":
                        file_bytes.read(2)
                    elif case_type == "\x01":
                        file_bytes.read(2) # Possible Bug: In SSQE, reads only 2 bytes from 16 sized buffer...
                    break
                elif id[0] == "\x08":
                    self._GetNextVariableString(file_bytes)
                    break
                elif id[0] == "\x09": # Custom difficulty. NOT FULLY IMPLEMENTED
                    if self.strict:
                        warn("Custom difficulty in V2 and V1 Not fully supported. Was found in sspm. View raw form by using .CustomDifficulty @self", Warning)
                    self.CustomDifficulty = self._GetNextVariableString(file_bytes)
                    
                elif id[0] == "\x0a":
                    self._GetNextVariableString(file_bytes, fourbytes=True) # BUG: Make sure to implement fourbytes method here. Shouldnt cause issues right now...
                    break
                elif id[0] == "\x0b":
                    warn("CustomBlocks in V2 and V1 Not supported. Was found in sspm.", Warning)
                    self._GetNextVariableString(file_bytes, fourbytes=True) # BUG: Make sure to implement fourbytes method here.
                    break
                elif id[0] == "\x0c": # no more PLEASEEE
                    warn("CustomBlocks in V2 and V1 Not supported. Was found in sspm.", Warning)

                    file_bytes.read(1)
                    value_length = file_bytes.read(4)
                    value_length_f = np.uint32(value_length)
                    
                    file_bytes.read(value_length_f) # I hope???
                    break

        except Exception as e:
            if self.strict:
                warn("Couldnt properly read customData in V2/V1 sspm. Fell back to audio pointer", BytesWarning)

        if self.contains_audio[0] == 1:
            # If all fails, fallback to audio pointer
            self.audioOffsetF = np.int64(int.from_bytes(self.audioOffset, byteorder='little'))
            
            # Get pointer from bytes
            file_bytes.seek(self.audioOffsetF)

        # reading optional data...
        #print(self.contains_audio[0])
        if self.contains_audio[0] == 1: # found audio
            self.totalAudioLengthF = np.int64(int.from_bytes(self.audioLength, 'little'))
            
            self.audio_bytes = file_bytes.read(self.total_audio_length_f)
            #print(file_bytes.tell())

        if self.contains_cover[0] == 1: # True
            self.totalCoverLengthF = np.int64(int.from_bytes(self.coverLength, 'little'))
            #print(self.totalCoverLengthF)
            self.cover_bytes = file_bytes.read(self.total_cover_length_f)
            #print(file_bytes.tell())


        # LAST ANNOYING PART!!!!!! MARKERS..
        self.mapData = self.map_id

        # Reading markers
        self.has_notes = False
        num_definitions = file_bytes.read(1)
        #print(numDefinitions[0])

        for i in range(num_definitions[0]): # byte form
            definition = self._GetNextVariableString(file_bytes)#, encoding="UTF-8")
            self.has_notes |= definition == "ssp_note" and i == 0 # bitwise shcesadnigans (its 1:30am for me)

            num_values = file_bytes.read(1)

            definition_data = int.from_bytes(b"\x01", 'little')
            while definition_data != int.from_bytes(b"\x00", 'little'): # Read until null BUG HERE
                definition_data = int.from_bytes(file_bytes.read(1), 'little')
        
        if not self.has_notes: # No notes
            return self.map_data
        
        # process notes
        #print("| | |", file_bytes.tell())
        note_count_f = np.uint32(int.from_bytes(self.note_count, 'little'))
        Notes = []
        is_quantum_checker = False

        for i in range(note_count_f): # Could be millions of notes. Make sure to keep optimized
            ms = file_bytes.read(4)
            marker_type = file_bytes.read(1)
            #print(file_bytes.tell())
            
            is_quantum = int.from_bytes(file_bytes.read(1), 'little')
            

            x_f = None
            y_f = None

            if is_quantum == 0:
                x = int.from_bytes(file_bytes.read(1), 'little')
                y = int.from_bytes(file_bytes.read(1), 'little')
                x_f = x
                y_f = y

            else:
                is_quantum_checker = True

                x = file_bytes.read(4)
                y = file_bytes.read(4)

                x_f = np.frombuffer(x, dtype=np.float32)[0]
                y_f = np.frombuffer(y, dtype=np.float32)[0]

                #xF = np.single(x) # numpy in clutch ngl
                #yF = np.single(y)
            
            ms_f = np.uint32(int.from_bytes(ms, 'little'))

            Notes.append((x_f, y_f, ms_f)) # F = converted lol

        self.Notes = sorted(Notes, key=lambda n: n[2]) # Sort by time
        self.is_quantum = is_quantum_checker

        return self

    def NOTES2TEXT(self) -> str:
        """
        Converts Notes to the standard sound space text file form. Commonly used in Roblox sound space
        """
        text_string = ''
        for x, y, ms in self.Notes:
            if text_string == '':
                text_string+=f",{x}|{y}|{ms}"
            else:
                text_string+=f",{x}|{y}|{ms}"
            
        return text_string

