from hashlib import sha1
from typing import BinaryIO
from warnings import warn

import numpy as np
from pysspm import SSPM, Header

def _ProcessSSPMV2(fileBytes: BinaryIO, header: Header, _use_strict: bool = False) -> SSPM:

    def _GetNextVariableString(data: BinaryIO, fourbytes: bool = False, encoding: str = "utf-8", V2: bool = True) -> str: # if it works it works..
        # Read 2 bytes for length
        length_bytes = data.read(2 if V2 else 1)
        #print(length_bytes)
            
        # Convert the length bytes to an integer | Bugfix reading improper data
        lengthF = np.int32(int.from_bytes(length_bytes, byteorder='little')) if fourbytes else np.int16(int.from_bytes(length_bytes, byteorder='little'))
            
        # Read the string of the determined length
        finalString = data.read(lengthF)
        try: # game changed encoding to support BOTH ASCII & UTF-8
            fsd = finalString.decode(encoding=encoding)
        except:
            fsd = finalString.decode(encoding='ASCII')
        
        return fsd
    
    # our main class, i'll refactor most variables from function inside here to save memory by double variables

    uses_ai: bool

    # static metadata
    Hash = fileBytes.read(20)
    #fileBytes.read(4) # buffer zone
    last_ms = int.from_bytes(fileBytes.read(4), 'little') # 32bit uint
    noteCount = fileBytes.read(4) # 32bit uint
    markerCount = fileBytes.read(4) # No clue what this is, ill figure it out | 32bit uint
    
    difficulty      = fileBytes.read(1)[0] # 0x00 01 02 03 04 05
    map_rating      = fileBytes.read(2)[0] # 16bit uint
    contains_audio  = True if fileBytes.read(1)[0] == 1 else False # 0x00 01?
    contains_cover  = True if fileBytes.read(1)[0] == 1 else False # 0x00 01?
    requires_mod     = True if fileBytes.read(1)[0] == 1 else False # 0x00 01?

    # pointers | If not present then is left as 8 bytes of 0
    custom_data_offset      = fileBytes.read(8)
    custom_dataLength       = fileBytes.read(8)
    audioOffset             = fileBytes.read(8) #if contains_audio else None
    audioLength             = fileBytes.read(8) #if contains_audio else None
    coverOffset             = fileBytes.read(8) #if contains_cover else None
    coverLength             = fileBytes.read(8) #if contains_cover else None
    markerDefinitionsOffset = fileBytes.read(8)
    markerDefinitionsLength = fileBytes.read(8)
    markerOffset            = fileBytes.read(8)
    markerLength            = fileBytes.read(8)

    # VariableLength Items..
    map_id      = _GetNextVariableString(fileBytes).replace(",", "")
    map_name    = _GetNextVariableString(fileBytes)
    song_name   = _GetNextVariableString(fileBytes)

    for i in range(len(map_id)): # getting mapID
        if map_id[i] in SSPM.INVALID_CHARS: # Create invalidChars thing
            map_id = map_id[:i] + '_' + map_id[i+1:]
    
    mapperCount = fileBytes.read(2)
    mapper_countFloat = int.from_bytes(mapperCount, byteorder="little") #np.uint16(mapperCount)
    mappers = [] # for now
    
    for i in range(mapper_countFloat): # Can have multiple mappers in a file.
        
        if True:
            mappers.append(_GetNextVariableString(fileBytes)) # Bugfix: supports uft-8 encoding for other langs
    try:
        # Oh god Custom data.... | Only supports custom difficulty thus far
        custom_data = fileBytes.read(2) 
        custom_data_total_length = np.uint16(custom_data)
        
        for i in range(custom_data_total_length):
            field = _GetNextVariableString(fileBytes)
            id = fileBytes.read(1)
            match id[0]:
                case 0:
                    continue
                case 1:
                    fileBytes.read(1) # skipping
                case 2:
                    fileBytes.read(2) # skipping
                case 3:
                    pass # will implement later
                case 4:
                    pass # will implement later
                case 5:
                    fileBytes.read(4) # skipping
                case 6:
                    fileBytes.read(8) # skipping
                case 7:
                    caseType = fileBytes.read(1)
                    if caseType == "\x00":
                        fileBytes.read(2)
                    elif caseType == "\x01":
                        fileBytes.read(2) # Possible Bug: In SSQE, reads only 2 bytes from 16 sized buffer...
                    break
                case 8:
                    _GetNextVariableString(fileBytes) # will support later
                case 9:
                    if _use_strict:
                        warn("Custom difficulty in V2 and V1 Not fully supported. Was found in sspm. View raw form by using .CustomDifficulty @self", Warning)
                    custom_difficulty = _GetNextVariableString(fileBytes)
                case 10:
                    _GetNextVariableString(fileBytes, fourbytes=True)
                case 11:
                    if _use_strict:
                        warn("Custom difficulty in V2 and V1 Not fully supported. Was found in sspm. View raw form by using .CustomDifficulty @self", Warning)
                    custom_difficulty = _GetNextVariableString(fileBytes)
                case 12:
                    if _use_strict:
                        warn("CustomBlocks in V2 and V1 Not supported. Was found in sspm.", Warning)

                    fileBytes.read(1)
                    valueLength = fileBytes.read(4)
                    valueLengthF = np.uint32(valueLength)
                    
                    fileBytes.read(valueLengthF) # I hope im handling this correctly
                case 13: # soon to be the newest and very important case: Tag marker for any maps made with AI/ML
                    uses_ai = True # very important soon

    except Exception as e:
        if _use_strict:
            warn("Couldnt properly read customData in V2/V1 sspm. Fell back to audio pointer", BytesWarning)

    audio_bytes=b''
    if contains_audio:
        # If all fails, fallback to audio pointer
        audioOffsetF = np.int64(int.from_bytes(audioOffset, byteorder='little'))    
        # Get pointer from bytes
        fileBytes.seek(audioOffsetF)
    
        # read audio from fallback point
        totalAudioLengthF = np.int64(int.from_bytes(audioLength, 'little'))
        audio_bytes = fileBytes.read(totalAudioLengthF)

    cover_bytes= b''
    if contains_cover:
        totalCoverLengthF = np.int64(int.from_bytes(coverLength, 'little'))
        cover_bytes = fileBytes.read(totalCoverLengthF)
    

    # LAST ANNOYING PART!!!!!! MARKERS..
    mapData = map_id

    # Reading markers
    hasNotes = False
    numDefinitions = fileBytes.read(1)
    #print(numDefinitions[0])

    for i in range(numDefinitions[0]): # byte form
        definition = _GetNextVariableString(fileBytes)#, encoding="UTF-8")
        hasNotes |= definition == "ssp_note" and i == 0 # bitwise operation | whyyyyyyyyyyyy.

        numValues = fileBytes.read(1)

        definitionData = int.from_bytes(b"\x01", 'little')
        while definitionData != int.from_bytes(b"\x00", 'little'): # Read until null BUG HERE
            definitionData = int.from_bytes(fileBytes.read(1), 'little')
    
    if not hasNotes: # No notes
        return mapData
    
    # process notes
    #print("| | |", fileBytes.tell())
    noteCountF = np.uint32(int.from_bytes(noteCount, 'little'))
    notes = []
    isQuantumChecker = False

    for i in range(noteCountF): # Could be millions of notes. Make sure to keep optimized
        ms = fileBytes.read(4)
        markerType = fileBytes.read(1)
        #print(fileBytes.tell())
        
        isQuantum = int.from_bytes(fileBytes.read(1), 'little')
        

        xF = None
        yF = None

        if isQuantum == 0:
            x = int.from_bytes(fileBytes.read(1), 'little')
            y = int.from_bytes(fileBytes.read(1), 'little')
            xF = x
            yF = y

        else:
            isQuantumChecker = True

            x = fileBytes.read(4)
            y = fileBytes.read(4)

            xF = np.frombuffer(x, dtype=np.float32)[0]
            yF = np.frombuffer(y, dtype=np.float32)[0]

            #xF = np.single(x) # numpy in clutch ngl
            #yF = np.single(y)
        
        msF = np.uint32(int.from_bytes(ms, 'little'))

        notes.append((xF, yF, msF)) # F = converted lol

    notes = sorted(notes, key=lambda n: n[2]) # Sort by time
    isQuantum = isQuantumChecker

    
    return SSPM(
        note_hash=Hash, 
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
        quantum=isQuantum,
        _use_strict=_use_strict
        ) 

def write_sspm(sspm: SSPM, filename: str = None, forcemapid=False, debug: bool = False, **kwargs) -> bytes: # FIX THIS CODE UP
    """
    Alternate wrapper function for writing in SSPM.
    
    Note: It is preferred you use `SSPM.write_sspm(location)` instead.
    """

    for key, value in kwargs.items(): # For extensive capabilities. Taken from StackOverflow :)
        if hasattr(sspm, key):
            setattr(sspm, key, value)
        else:
            warn(f"{key} is not a valid attribute", Warning)


    header = bytes([ # base header
        0x53, 0x53, 0x2b, 0x6d, # File type signature "SS+M"
        0x02, 0x00, # SSPM format version (0x02 or 0x01) Set to 2 by default
        0x00, 0x00, 0x00, 0x00, # 4 byte reserved space.
    ])


    # configs
    contains_cover = b"\x01" if sspm.cover_bytes else b"\x00" # 0 or 1
    contains_audio = b"\x01" if sspm.audio_bytes else b"\x00" # 0 or 1
    requires_mod = b"\x01" if sspm.requires_mod else b"\x00" # Who actually uses this though?
    
    #print(self.Notes[-1][2])
    
    last_ms = np.uint32(sspm.notes[-1][2]).tobytes()  # np.uint32 object thus far | 4 bytes | base before getting proper one
    note_count = np.uint32(len(sspm.notes)).tobytes() # bytes should be length of 4
    marker_count = note_count # nothing changes from what I get from documentation..?

    difficulty: bytes = sspm.difficulty.value.to_bytes(1, 'little')

    if debug:
        print("Metadata loaded")

    # good until here
    #self.map_id = 
    song_name = "Pysspm2 Default".encode("utf-8") if not sspm.song_name else sspm.song_name.encode("utf-8") # bugfix: misread documentation utf support

    if not forcemapid:
        map_id = f"{'_'.join(sspm.mappers)}_{sspm.map_name.replace(' ', '_')}".encode("utf-8") # combines mappers and map name to get the id.
    else:
        map_id = sspm.map_id.encode("utf-8")
        
    map_id_length = len(map_id).to_bytes(2, 'little')
    map_name = sspm.map_name.encode("utf-8")
    map_name_length = len(sspm.map_name).to_bytes(2, 'little')
    song_name_length = len(sspm.song_name).to_bytes(2, 'little')

    mapper_count_length = len(sspm.mappers).to_bytes(2, 'little')
    
    #self.mappersf = '\n'.join(self.mappers).encode('ASCII') # Possible bug | maybe include breakchar like \n
    mappers_bytestring = bytearray() # hold encoded mapper list

    for mapper in sspm.mappers:
        # process string magic
        _mapper_bytes = mapper.encode('utf-8')
        _mapper_length = len(_mapper_bytes).to_bytes(2, 'little') # get byte length
        _mapper_final = _mapper_length + _mapper_bytes
        
        # Append to the mappersf byte array
        mappers_bytestring.extend(_mapper_final)

    mappers_bytestring = bytes(mappers_bytestring) # convert to regular bytes

    final_string = map_id_length+map_id+map_name_length+map_name+song_name_length+song_name+mapper_count_length+mappers_bytestring # merge values into a string because we are done with this section
    
    if debug:
        print("Strings loaded")

    # FEATURE REQUEST: Add support for custom difficulty here.
    custom_data = b"\x00\x00" # 2 bytes, no custom data supported right neoww

    # Pointer locations in byte array
    if debug:
        print("1/2 pointers loaded. Note creation next")

    
    total_notes = len(sspm.notes)
    markers = bytearray()
    lastms = 0

    count = 0
    for note_x, note_y, note_ms in sspm.notes: # update: updated variables for readability
        count += 1
        
        if debug and count % 1000 == 0:
            print(f"Notes completed: {count}/{total_notes}", end="\r", flush=True)
        
        rounded_nx = round(note_x) # don't question this approach :D
        rounded_ny = round(note_y)
        rounded_nx_2 = round(note_x, 2)
        rounded_ny_2 = round(note_y, 2)
        
        # Calculate the bytes
        ms_bytes = np.uint32(note_ms + sspm.export_offset).tobytes()
        marker_type = b'\x00'
        identifier = b'\x00' if (rounded_nx == rounded_nx_2 and rounded_ny == rounded_ny_2) else b'\x01'
        
        if identifier == b'\x00':
            x_bytes = np.uint16(rounded_nx).tobytes()[0:1]
            y_bytes = np.uint16(rounded_ny).tobytes()[0:1]
        else:
            x_bytes = np.float32(note_x).tobytes()
            y_bytes = np.float32(note_y).tobytes()
        if lastms < note_ms: # notes dont need to be in order--only ms needs to be known
            lastms = note_ms
        
        final_marker = ms_bytes + marker_type + identifier + x_bytes + y_bytes
        markers.extend(final_marker)
    
    last_ms = np.uint32(lastms).tobytes() # because list is not in order.

    if debug:
        print("All pointers finished")


    # adding everything together
    map_rating = b"\x00\x00" # N/A for now..
    metadata = last_ms + note_count + marker_count + difficulty + map_rating + contains_audio + contains_cover + requires_mod # level rating Not fully implemented yet 
    
    offset = len(header) + 20 + len(metadata) + 80 + len(final_string) # header, hash[20], metadata, offsets*10[8] + string_data
    
    # Pointer logic explained:
    # offset is a pointer value for reading memory
    # we initialize it assuming all pointers are used, and subtract if one isnt used.
    # I could fully refactor but thats just too much work.

    # Root cause of issues is this pointer
    custom_data_offset = np.uint64(offset).tobytes()
    custom_data_length = np.uint64(len(custom_data)).tobytes()
    offset+= len(custom_data)

    # bugfix: Misread documentation
    audio_offset = np.uint64(offset).tobytes() if sspm.audio_bytes else b'\x00\x00\x00\x00\x00\x00\x00\x00'
    audio_length = np.uint64(len(sspm.audio_bytes)).tobytes() if sspm.audio_bytes else b'\x00\x00\x00\x00\x00\x00\x00\x00'
    offset+= len(sspm.audio_bytes) if sspm.audio_bytes else 8
    #sspm.audio_bytes

    cover_offset = np.uint64(offset).tobytes() if sspm.cover_bytes else b'\x00\x00\x00\x00\x00\x00\x00\x00'
    cover_length = np.uint64(len(sspm.cover_bytes)).tobytes() if sspm.cover_bytes else b'\x00\x00\x00\x00\x00\x00\x00\x00'
    offset+= len(sspm.cover_bytes) if sspm.cover_bytes else 8
    #sspm.cover_bytes

    note_definition = "ssp_note".encode("ASCII")
    note_definition_bytestring = len(note_definition).to_bytes(2, 'little') + note_definition
    marker_definition_start = b"\x01"
    makert_definition_end = b"\x01\x07\x00" # var markerDefEnd = new byte[] { 0x01, /* one value */ 0x07, /* data type 07 - note */ 0x00 /* end of definition */ };

    marker_definition_bytestring = marker_definition_start+note_definition_bytestring+makert_definition_end
    marker_definition_offset = np.uint64(offset).tobytes()
    marker_definition_length = np.uint64(len(marker_definition_bytestring)).tobytes()
    offset+=len(marker_definition_bytestring)

    # notes n stuff
    marker_offset = np.uint64(offset).tobytes()
    marker_length = np.uint64(len(markers)).tobytes()

    # hashing
    marker_hash = sha1(marker_definition_bytestring+markers).digest()

    pointers = b''
    pointers+=custom_data_offset+custom_data_length+audio_offset+audio_length+cover_offset+cover_length+marker_definition_offset+marker_definition_length+marker_offset+marker_length

    if debug:
        print(last_ms)
        print(metadata)
        print(pointers)
        print(final_string)
        print(custom_data)
        print(sspm.audio_bytes[0:10])
        print(sspm.cover_bytes[0:10])

    sspm_bytes = header+marker_hash+metadata+pointers+final_string+custom_data+sspm.audio_bytes+sspm.cover_bytes+marker_definition_bytestring+markers
    
    if filename:
        with open(filename, 'wb') as f:
            f.write(sspm_bytes)
        return None
    
    return sspm_bytes



def _ProcessSSPMV1(self, fileBytes: BinaryIO):
    """
    Fog's implementation of SSPMV1 reader. To be refactored

    Warning: Will raise error if used!
    """

    raise NotImplementedError("SSPMV1 support for PYSSPM version 2.0+ is not supported yet. Use versions pre-2.0 for SSPMV1 read support")


    # start of metadata

    self.map_id = self._NewLineTerminatedString(fileBytes).replace(",", "")
    self.map_name = self._NewLineTerminatedString(fileBytes)
    self.song_name = self.map_name # lol
    self.mappers = self._NewLineTerminatedString(fileBytes).split(", ") # mappers arent in an array, so i will just split

    self.last_ms = fileBytes.read(4)
    self.noteCount = fileBytes.read(4)
    self.difficulty = fileBytes.read(1)

    # end of metadata
    
    # start of file data

    self.coverType = int.from_bytes(fileBytes.read(1), byteorder='little')

    self.contains_cover = None
    self.coverLength = None
    self.coverBytes = None

    match self.coverType:
        case 2: # PNG
            self.contains_cover = b"\x01"

            self.coverLength = fileBytes.read(8)
            coverLengthtoInt = np.int64(int.from_bytes(self.coverLength, 'little'))

            self.coverBytes = fileBytes.read(coverLengthtoInt)
        case _: # for no cover, or non supported format
            self.contains_cover = b"\x00"

    self.audioType = int.from_bytes(fileBytes.read(1), 'little')

    self.contains_audio = None
    self.audioLength = None
    self.audioBytes = None

    match self.audioType:
        case 0: # no Audio
            self.contains_audio = b"\x00"
        case 1: # Audio! :)
            self.contains_audio = b"\x01"

            self.audioLength = fileBytes.read(8)
            audioLengthtoInt = int.from_bytes(self.audioLength, 'little')

            self.audioBytes = fileBytes.read(audioLengthtoInt) # must be mp3 or OGG

    # end of file data

    # start of note data

    noteCounttoInt = int.from_bytes(self.noteCount, 'little')
    Notes = []
    isQuantumChecker = False

    for i in range(noteCounttoInt):
        ms = fileBytes.read(4)
        
        # i can just copy and paste the rest of this since its the same

        isQuantum = int.from_bytes(fileBytes.read(1), 'little')

        xF = None
        yF = None

        if isQuantum == 0:
            x = int.from_bytes(fileBytes.read(1), 'little')
            y = int.from_bytes(fileBytes.read(1), 'little')
            xF = x
            yF = y

        else:
            isQuantumChecker = True

            x = fileBytes.read(4)
            y = fileBytes.read(4)

            xF = np.frombuffer(x, dtype=np.float32)[0]
            yF = np.frombuffer(y, dtype=np.float32)[0]
        
        msF = np.uint32(int.from_bytes(ms, 'little'))

        Notes.append((xF, yF, msF))

    
    self.Notes = sorted(Notes, key=lambda n: n[2]) # Sort by time
    self.isQuantum = isQuantumChecker

    return self


if __name__ == "__main__": # test for myself
    from pysspm_rhythia.pysspm import read_sspm, SSPM
    with open(r"D:\Python\customLibs\pysspm_rhythia\tests\TestSong.mp3", "rb") as f:
        SHAREDAUDIO = f.read()

    read_sspm(r"C:\Users\david\AppData\Roaming\SoundSpacePlus\maps\ss_archive_missio_-_dizzy.sspm")
    
    SSPM(difficulty="easy", audio_bytes=SHAREDAUDIO, map_name="Test run level", mappers=["Test_Pysspm_Rhythia", "Test"], notes=[(0, 0, 150), (1, 2, 590), (1.2, 0.5, 1500)]).write(r"D:\Python\customLibs\pysspm_rhythia\tests\test_write_n_cover.sspm", debug=True)
    #parser.WriteSSPM(coverBytes=None, audioBytes=SHAREDAUDIO, Difficulty="N/A", mapName="Test run level", mappers=["Test_Pysspm_Rhythia", "Test"], Notes=SHAREDNOTES)
    print("write test_write_sspm_from_scratch_no_cover")

    sspmp = read_sspm(r"D:\Python\customLibs\pysspm_rhythia\tests\test_write_n_cover.sspm")
    print(sspmp.__str__())