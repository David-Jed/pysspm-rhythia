import pandas as pd
import pytest
import importlib.util
import sys
import os

# Define the path to pysspm_rhythia.py
pysspm_rhythia_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'pysspm_rhythia', 'pysspm.py'))

# Load the module dynamically
spec = importlib.util.spec_from_file_location("pysspm", pysspm_rhythia_path)
pysspm_rhythia = importlib.util.module_from_spec(spec)
sys.modules["pysspm"] = pysspm_rhythia
spec.loader.exec_module(pysspm_rhythia)


SHAREDNOTES = [(1, 1, 500), (0, 1, 250), (2, 0, 1500)]
with open("./tests/TestSong.mp3", "rb") as f:
    SHAREDAUDIO = f.read()
with open("./tests/TestCover.png", "rb") as f:
    SHAREDCOVER = f.read()

# function for using pytest
def test_read_sspm(): # Basic reading of sspm file format
    chart = pysspm_rhythia.read_sspm("./tests/Test.sspm")
    assert len(chart.notes) > 0

# now we read and write the notes to a new sspm file.
def test_read_write_sspm(): # Writing a new SSPM file from parsed notes
    first = pysspm_rhythia.read_sspm("./tests/Test.sspm")
    first.write_sspm("./tests/Test2.sspm", map_name="KOCMOC_MAP_TESTING_SSPMLIB")
    second = pysspm_rhythia.read_sspm("./tests/Test.sspm")

    # comparing values between first and second. should all be the same
    assert first.audio_bytes == second.audio_bytes
    assert first.audio_bytes == second.audio_bytes
    print("Audio checked")
    assert first.notes == second.notes
    print("Notes checked")
    assert first.last_ms == second.last_ms
    assert first.last_ms == second.last_ms
    print("lastMs checked")
    assert first.cover_bytes == second.cover_bytes
    print("coverBytes checked")

    #parser = SSPMParser()
    #first = parser.ReadSSPM("./tests/Test.sspm")
    #parser.WriteSSPM("./tests/Test2.sspm", mapName="KOCMOC_MAP_TESTING_SSPMLIB", audioBytes=SHAREDAUDIO, coverBytes=SHAREDCOVER)
    #second = parser.ReadSSPM("./tests/Test.sspm")

# This last test starts from scratch, and applies all the values into the write function.
def test_write_sspm_from_scratch_no_cover(): # Writing a new SSPM file from scratch
    pysspm_rhythia.SSPM(difficulty="easy", audio_bytes=SHAREDAUDIO, map_name="Test run level", mappers=["Test_Pysspm_Rhythia", "Test"], notes=SHAREDNOTES).write("./tests/test_write_n_cover.sspm")
    #parser.WriteSSPM(coverBytes=None, audioBytes=SHAREDAUDIO, Difficulty="N/A", mapName="Test run level", mappers=["Test_Pysspm_Rhythia", "Test"], Notes=SHAREDNOTES)
    print("write test_write_sspm_from_scratch_no_cover")
    pysspm_rhythia.read_sspm("./tests/test_write_n_cover.sspm")

def test_write_sspm_from_scratch_no_audio(): # Writing a new SSPM file from scratch
    pysspm_rhythia.SSPM(difficulty="easy", cover_bytes=SHAREDCOVER, map_name="Test run level", mappers=["Test_Pysspm_Rhythia", "Test"], notes=SHAREDNOTES).write("./tests/test_write_n_audio.sspm")
    #parser.WriteSSPM(coverBytes=None, audioBytes=SHAREDAUDIO, Difficulty="N/A", mapName="Test run level", mappers=["Test_Pysspm_Rhythia", "Test"], Notes=SHAREDNOTES)
    print("write test_write_sspm_from_scratch_n_audio")
    pysspm_rhythia.read_sspm("./tests/test_write_n_audio.sspm")

def test_write_sspm_from_scratch_no_cover_audio(): # Writing a new SSPM file from scratch
    pysspm_rhythia.SSPM(difficulty="easy", map_name="Test run level", mappers=["Test_Pysspm_Rhythia", "Test"], notes=SHAREDNOTES).write("./tests/test_write_n_audio_cover.sspm")
    #parser.WriteSSPM(coverBytes=None, audioBytes=SHAREDAUDIO, Difficulty="N/A", mapName="Test run level", mappers=["Test_Pysspm_Rhythia", "Test"], Notes=SHAREDNOTES)
    print("write test_write_sspm_from_scratch_n_audio_cover")
    pysspm_rhythia.read_sspm("./tests/test_write_n_audio_cover.sspm")

def test_EXTRAS_conversion():
    chart = pysspm_rhythia.read_sspm("./tests/test_write_n_audio_cover.sspm")
    notes_text = chart.NOTES2TEXT()
    print(notes_text)
    assert notes_text == ",0|1|250,1|1|500,2|0|1500" or notes_text == "0|1|250,1|1|500,2|0|1500" # UPDATED: now automatically sorts by time

def test_EXTRAS_PP_Calc_V1():
    print("W.I.P")
    assert 1==1

def test_EXTRAS_MappingStyle_Vision():
    print("W.I.P")
    assert 1==1


"""

# Read the SSPM file and parse it into a list of notes. | old stuff
parser.ReadSSPM("./tests/Test.sspm")
print(len(parser.Notes))
print(parser.Notes[1000:1020])
#parser.mapName = "KOCMOC_MAP_TESTING_SSPMLIB"
parser.WriteSSPM("./tests/Test2.sspm", mapName="KOCMOC_MAP_TESTING_SSPMLIB")

parser.ReadSSPM("./tests/Test2.sspm") # if we can open it again then its good.
print("-----------------------")
print(len(parser.Notes))
print(parser.Notes[1000:1020])

"""