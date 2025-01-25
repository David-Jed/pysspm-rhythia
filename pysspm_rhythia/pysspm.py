from io import BytesIO
from hashlib import sha1
from types import NoneType
from typing import BinaryIO
import numpy as np
from warnings import warn


# TODO: (In order of priority)
# Add typing support for library ✔️
# add proper documentation on github
# add proper documentation in code ✔️
# add loading of sspmV2  ✔️
# add support for creating sspmV2 ✔️
# clean up unused variables from @self ✔️
# add support for sspmv1 loading
# support multiple version of sspm
# add custom block support in loading
# fix small bugs...

"""
Stolen from the SSQE version lol
            var data = new List<byte>(); // final converted data
            data.AddRange(header);
            data.AddRange(hash);
            data.AddRange(metadata);
            data.AddRange(pointers);
            data.AddRange(strings);
            data.AddRange(customData);
            data.AddRange(audio);
            data.AddRange(cover);
            data.AddRange(markerDefinitions);
            data.AddRange(markers);
            return data.ToArray();
"""

class SSPMParser:
    """
    # SSPM Reader

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
        self.export_offset = 0
        self.Header = bytes([ # base header
            0x53, 0x53, 0x2b, 0x6d, # File type signature "SS+M"
            0x02, 0x00, # SSPM format version (0x02 or 0x01) Set to 2 by default
            0x00, 0x00, 0x00, 0x00, # 4 byte reserved space.
        ])
        self.last_ms = None
        self.metadata = {}
        self.song_name = None
        self.requires_mod = 0
        self.strict = False
        self.cover_bytes = None
        self.Difficulty = 0
        self.audio_bytes = None
        self.map_name = None
        self.mappers = None
        self.Notes = None
        self.map_ID = None
        self.custom_data_offset = 0

    def _GetNextVariableString(self, data: BinaryIO, fourbytes: bool = False, encoding: str = "ASCII", V2: bool = True) -> str: # Why did this have a self variable??
        # Read 2 bytes for length (assuming little-endian format)
        length_bytes = data.read(2 if V2 else 1)
        
        # Convert the length bytes to an integer | Bugfix reading improper data
        length_f = np.int32(int.from_bytes(length_bytes, byteorder='little')) if fourbytes else np.int16(int.from_bytes(length_bytes, byteorder='little'))
        
        # Read the string of the determined length
        final_string = data.read(length_f)
        
        return final_string.decode(encoding=encoding)
    
    def _NewLineTerminatedString(self, data: BinaryIO, encoding: str = "ASCII") -> str: # for SSPMv1

        final_string = bytearray()
        while True:
            stringbyte = data.read(1) # keep going by one bit
            if stringbyte == b'\n': # once it reaches a new line, break
                break
            final_string.extend(stringbyte)
        
        return final_string.decode(encoding=encoding)

    
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
        self.contains_cover = b"\x01" if self.cover_bytes != None else b"\x00" # 0 or 1
        self.contains_audio = b"\x01" if self.audio_bytes != None else b"\x00" # 0 or 1
        self.requires_mod = b"\x01" if self.requires_mod == 1 or self.requires_mod == b"\x01" else b"\x00" # Who actually uses this though?
        
        #print(self.Notes[-1][2])
        self.last_ms = np.uint32(self.Notes[-1][2]).tobytes()  # np.uint32 object thus far | 4 bytes | base before getting proper one
        self.note_count = np.uint32(len(self.Notes)).tobytes() # bytes should be length of 4
        self.marker_count = self.note_count # nothing changed from last time

        self.Difficulty = self.Difficulty if self.DIFFICULTIES.get(self.Difficulty) == None else self.DIFFICULTIES.get(self.Difficulty)
        self.Difficulty = self.Difficulty.to_bytes(1, 'little') if isinstance(self.Difficulty, int) else self.Difficulty

        if debug:
            print("Metadata loaded")

        # good until here
        #self.mapID = 
        self.song_name = "sspmLib Song - author".encode("ASCII") if not self.song_name else self.song_name.encode("ASCII")

        if not forcemapid:
            self.map_ID = f"{'_'.join(self.mappers)}_{self.map_name.replace(' ', '_')}".encode("ASCII") # combines mappers and map name to get the id.
        else:
            self.map_ID = self.map_ID.encode("ASCII")
            
        self.map_ID_f = len(self.map_ID).to_bytes(2, 'little')
        self.map_name = self.map_name.encode("ASCII")
        self.map_name_f = len(self.map_name).to_bytes(2, 'little')
        self.song_name_f = len(self.song_name).to_bytes(2, 'little')

        self.mapper_count_f = len(self.mappers).to_bytes(2, 'little')
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

        self.strings = self.map_ID_f+self.map_ID+self.map_name_f+self.map_name+self.song_name_f+self.song_name+self.mapper_count_f+self.mappers_f # merge values into a string because we are done with this section
        if debug:
            print("Strings loaded")

        self.custom_data = b"\x00\x00" # 2 bytes, no custom data supported right neoww

        # FEATURE REQUEST: Add support for custom difficulty here.

        # Pointer locations in byte array

        
        if debug:
            print("1/2 pointers loaded. Note creation next")

        self.Markers = b''

        """ # Old slow code. Keep in case
        count = 0
        totalNotes = len(self.Notes)
        for nx, ny, nms in self.Notes:
            count+=1
            if debug and count % 1000 == 0:
                print(f"Notes completed: {count}/{totalNotes}", end="\r", flush=True)
            # Equivalent to: BitConverter.GetBytes((uint)(note.Ms + exportOffset))
            ms = (np.uint32(nms + self.exportOffset)).tobytes()

            # Equivalent to: new byte[1] (initialized to 0x00)
            markerType = b'\x00'

            # Equivalent to: Math.Round(note.X) == Math.Round(note.X, 2)
            xyInt = round(nx) == round(nx, 2) and round(ny) == round(ny, 2)

            # Equivalent to: new byte[] { (byte)(xyInt ? 0x00 : 0x01) }
            identifier = b'\x00' if xyInt else b'\x01'

            # Equivalent to: Convert x and y based on whether they are integers
            if xyInt:
                x = np.uint16(round(nx)).tobytes()[0:1]
                y = np.uint16(round(ny)).tobytes()[0:1]
            else:
                x = np.float32(nx).tobytes()
                y = np.float32(ny).tobytes()

            # Equivalent to: Concatenate ms, markerType, identifier, x, and y
            finalMarker = ms + markerType + identifier + x + y

            # Add to the markers list
            self.Markers += finalMarker"""

        count = 0
        total_notes = len(self.Notes)
        
        markers = bytearray()
        last_ms = 0
        
        for nx, ny, nms in self.Notes:
            count += 1
            
            if debug and count % 1000 == 0:
                print(f"Notes completed: {count}/{total_notes}", end="\r", flush=True)
            
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
        metadata = self.last_ms + self.note_count + self.marker_count + self.Difficulty + b"\x00\x00" + self.contains_audio + self.contains_cover + self.requires_mod # level rating Not fully implemented yet 
        offset = len(self.Header) + 20 + len(metadata) + 80 + len(self.strings)
        # pointers
        self.custom_data_offset = np.uint64(offset).tobytes()
        self.custom_data_length = np.uint64(len(self.custom_data)).tobytes()
        offset+= len(self.custom_data)

        
        self.audio_offset = np.uint64(offset).tobytes()
        self.audio_length = np.uint64(len(self.audio_bytes)).tobytes() if self.contains_audio == b'\x01' else b'\x00\x00\x00\x00\x00\x00\x00\x00' # 8 bytes filler if no audio length found | Possible bug if no audio found, and reading special block fails. | may default to start of file.
        offset+= len(self.audio_bytes) if self.contains_audio == b'\x01' else len(b'\x00\x00\x00\x00\x00\x00\x00\x00') # 8
        self.audio_bytes = b'' if self.audio_bytes == None else self.audio_bytes

        self.cover_offset = np.uint64(offset).tobytes()
        self.cover_length = np.uint64(len(self.cover_bytes)).tobytes() if self.contains_cover == b'\x01' else b'\x00\x00\x00\x00\x00\x00\x00\x00' # 8 bytes filler if no audio length found 
        offset+= len(self.cover_bytes) if self.contains_cover == b'\x01' else len(b'\x00\x00\x00\x00\x00\x00\x00\x00') # 8
        self.cover_bytes = b'' if self.cover_bytes == None else self.cover_bytes

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
        pointers+=self.custom_data_offset+self.custom_data_length+self.audio_offset+self.audio_length+self.cover_offset+self.cover_length+self.marker_definitions_offset+self.marker_definitions_length+self.marker_offset+self.marker_length

        if debug:
            print(self.last_ms)
            print(metadata)
            print(pointers)
            print(self.strings)
            print(self.custom_data)
            print(self.audio_bytes[0:10])
            print(self.cover_bytes[0:10])

        self.SSPMData = self.Header+s_hash+metadata+pointers+self.strings+self.custom_data+self.audio_bytes+self.cover_bytes+self.marker_definitions+self.Markers
        
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
        self.note_count = file_bytes.read(4) # 32bit uint
        self.marker_count = file_bytes.read(4) # No clue what this is, ill figure it out | 32bit uint
        
        self.Difficulty = file_bytes.read(1) # 0x00 01 02 03 04 05
        self.map_rating = file_bytes.read(2) # 16bit uint
        self.contains_audio = file_bytes.read(1) # 0x00 01?
        self.contains_cover = file_bytes.read(1) # 0x00 01?
        self.requires_mod = file_bytes.read(1) # 0x00 01?

        # pointers | If not present then is left as 8 bytes of 0
        self.custom_data_offset = file_bytes.read(8)
        self.custom_data_length = file_bytes.read(8)
        self.audio_offset = file_bytes.read(8)
        self.audio_length = file_bytes.read(8)
        self.cover_offset = file_bytes.read(8)
        self.cover_length = file_bytes.read(8)
        self.marker_definitions_offset = file_bytes.read(8)
        self.marker_definitions_length = file_bytes.read(8)
        self.marker_offset = file_bytes.read(8)
        self.marker_length = file_bytes.read(8)

        # VariableLength Items..
        self.map_ID = self._GetNextVariableString(file_bytes).replace(",", "")
        self.map_name = self._GetNextVariableString(file_bytes)
        self.song_name = self._GetNextVariableString(file_bytes)

        for i in range(len(self.map_ID)): # getting mapID
            if self.map_ID[i] in self.INVALID_CHARS: # Create invalidChars thing
                self.map_ID = self.map_ID[:i] + '_' + self.map_ID[i+1:]
        
        mapper_count = file_bytes.read(2)
        self.mapper_count_float = int.from_bytes(mapper_count, byteorder="little") #np.uint16(mapperCount)
        self.mappers = [] # for now
        
        for i in range(self.mapper_count_float): # Can have multiple mappers in a file.
            
            if True:
            #try: # temporary solution until I figure out whats happening
                self.mappers.append(self._GetNextVariableString(file_bytes))
            #except:
            #    pass
        try:
            # Oh god Custom data.... | Only supports custom difficulty thus far
            custom_data = file_bytes.read(2) # ??
            self.custom_data_total_length = np.uint16(custom_data)
            
            for i in range(self.custom_data_total_length):
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
                        warn("Custom difficulty in V2 and V1 Not supported. Was found in sspm. View raw form by using .CustomDifficulty @self", Warning)
                    self.custom_difficulty = self._GetNextVariableString(file_bytes)
                    
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
    
        # If all fails, fallback to audio pointer
        self.audio_offset_f = np.int64(int.from_bytes(self.audio_offset, byteorder='little'))
        
        # Get pointer from bytes
        file_bytes.seek(self.audio_offset_f)

        # reading optional data...
        #print(self.containsAudio[0])
        if self.contains_audio[0] == 1: # found audio
            self.total_audio_length_f = np.int64(int.from_bytes(self.audio_length, 'little'))
            
            self.audio_bytes = file_bytes.read(self.total_audio_length_f)
            #print(fileBytes.tell())

        if self.contains_cover[0] == 1: # True
            self.total_cover_length_f = np.int64(int.from_bytes(self.cover_length, 'little'))
            #print(self.totalCoverLengthF)
            self.cover_bytes = file_bytes.read(self.total_cover_length_f)
            #print(fileBytes.tell())


        # LAST ANNOYING PART!!!!!! MARKERS..
        self.map_data = self.map_ID

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
        #print("| | |", fileBytes.tell())
        note_count_f = np.uint32(int.from_bytes(self.note_count, 'little'))
        Notes = []
        is_quantum_checker = False

        for i in range(note_count_f): # Could be millions of notes. Make sure to keep optimized
            ms = file_bytes.read(4)
            marker_type = file_bytes.read(1)
            #print(fileBytes.tell())
            
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

    
    def _ProcessSSPMV1(self, file_bytes: BinaryIO):
        """
        just going to note, i will be using some of the self variables
        for compatibility with SSPMv2 (such as containsAudio, etc), and 
        i will also be formatting theoutput like SSPMv2, such as splitting 
        mappers by comma to make it into an array

                                                                -fog
        """


        # start of metadata

        self.map_ID = self._NewLineTerminatedString(file_bytes).replace(",", "")
        self.map_name = self._NewLineTerminatedString(file_bytes)
        self.song_name = self.mapName # lol
        self.mappers = self._NewLineTerminatedString(file_bytes).split(", ") # mappers arent in an array, so i will just split

        self.last_ms = file_bytes.read(4)
        self.note_count = file_bytes.read(4)
        self.Difficulty = file_bytes.read(1)

        # end of metadata
        
        # start of file data

        self.cover_type = int.from_bytes(file_bytes.read(1), byteorder='little')

        self.contains_cover = None
        self.cover_length = None
        self.cover_bytes = None

        match self.cover_type:
            case 2: # PNG
                self.contains_cover = b"\x01"

                self.cover_length = file_bytes.read(8)
                cover_length_to_int = np.int64(int.from_bytes(self.coverLength, 'little'))

                self.cover_bytes = file_bytes.read(cover_length_to_int)
            case _: # for no cover, or non supported format
                self.contains_cover = b"\x00"

        self.audio_type = int.from_bytes(file_bytes.read(1), 'little')

        self.contains_audio = None
        self.audio_length = None
        self.audio_bytes = None

        match self.audio_type:
            case 0: # no Audio
                self.contains_audio = b"\x00"
            case 1: # Audio! :)
                self.contains_audio = b"\x01"

                self.audio_length = file_bytes.read(8)
                audio_length_to_int = int.from_bytes(self.audio_length, 'little')

                self.audio_bytes = file_bytes.read(audio_length_to_int) # must be mp3 or OGG

        # end of file data

        # start of note data

        note_count_to_int = int.from_bytes(self.note_count, 'little')
        Notes = []
        is_quantum_checker = False

        for i in range(note_count_to_int):
            ms = file_bytes.read(4)
            
            # i can just copy and paste the rest of this since its the same

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
            
            ms_f = np.uint32(int.from_bytes(ms, 'little'))

            Notes.append((x_f, y_f, ms_f))

        
        self.Notes = sorted(Notes, key=lambda n: n[2]) # Sort by time
        self.is_quantum = is_quantum_checker

        return self
        






"""    def _GetNextVariableString(self, data: BinaryIO, fourbytes: bool = False) -> str:
        length = data.read(2)
        length = length.rstrip("\x00")
        lengthF = np.uint32(length) if fourbytes else np.int16(length)
        
        finalString = data.read(lengthF)
        return finalString.decode("ASCII")
"""

"""
        bytes_list = []

        current_byte = data.read(1)

        while current_byte != b'\x0a':  # 0x0a is the ASCII code for newline ('\n')
            bytes_list.append(current_byte[0])
            current_byte = data.read(1)

        return bytes(bytes_list).decode('ascii') # ONLY SUPPORTS ASCII
"""


