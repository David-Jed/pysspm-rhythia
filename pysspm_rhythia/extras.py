"""
Collection of items I created that I thought I might import into the library in case anyone finds them useful
"""
from types import NoneType
import numpy as np
from collections import defaultdict
import math
from pysspm_rhythia.pysspm import SSPMParser

def calcObsiidRating(self: SSPMParser, notes: list = None) -> SSPMParser:
    """
    calculates difficulty by using Obsiids difficulty calculation.
    This method is essentially just the dot product of the notes
    """

    print(self.Notes[1:5])

    if not notes: # if we pass in notes
        pass
    raise NotImplementedError("CalcObsiidRating function is a W.I.P.")

    return self


def calcPPRating(self: SSPMParser) -> float:
    """
    This calculation method is the method used in rhythia-online. | May change in future updates
    """
    return len(self.Notes) / 100 

def calcStarRating(self: SSPMParser) -> float:
    """
    # Pseudo-code outline:

    - get notes [0, 0, 100, 1, 0, 150]
    - apply exponential decay (of some sorts)
    """

class Note:
    NOTECLASSES = {
        "spiral": ("broken-spiral", "short-slide", "medium-slide", "s-slide", "o-slide"), # cannot be jumpstream
        "jumpstream": ("tech", "vibro", "long-jump", "short-jump", "sidesteps", "corner-jumps", "star-jump", "rotate-jumps", "pinjumps"), # cannot be spiral
        "misc": ("stack", "meganote", "quantum", "offgrid") # fits under both spiral and jumpstream
    }

    def __init__(self, 
                 x: float | int = None, 
                 y: float | int = None, 
                 ms: int = None, 
                 note: tuple = None, 
                 hyp: float | int = None, 
                 vector: tuple = None, 
                 classifications: list = []) -> None:
        """_WORK IN PROGRESS_

        Args:
            x (float | int): _x value of the map note_
            y (float | int): _y value of the map note_
            ms (int): _milisecond value of the map note_
            note (tuple, optional): _tuple form of notes | overrides x, y, ms if used_. Defaults to None.
            hyp (float | int, optional): _hypotenuse of 2 points_. Defaults to None.
            vector (tuple, optional): _vector class done from classifications_. Defaults to None.
            classifications (tuple, optional): _classifications of notetype_. Defaults to None.

        Returns:
            None: _description_
        """
        

        
        # Set x, y, ms based on note tuple or defaults
        if note is not None:
            self.x, self.y, self.ms = note
        else:
            self.x = x
            self.y = y
            self.ms = ms
        
        # Set vector components (dx, dy, dt, dh)
        if vector is not None:
            self.dx, self.dy, self.dt, self.dh = vector
        else:
            self.dx = self.dy = self.dt = self.dh = 0

        self.note = (self.x, self.y, self.ms)
        # Classifications
        self.classifications = classifications



class NoteClassifier():
    NOTECLASSES = {
        "spiral": ("broken-spiral", "short-slide", "medium-slide", "s-slide", "o-slide"), # cannot be jumpstream
        "jumpstream": ("tech", "vibro", "long-jump", "short-jump", "sidesteps", "corner-jumps", "star-jump", "rotate-jumps", "pinjumps"), # cannot be spiral
        "misc": ("stack", "meganote", "quantum", "offgrid") # fits under both spiral and jumpstream
    }

    def __init__(self, notes, time_multiplier=5):
        """_WORK IN PROGRESS_

        Args:
            notes (_type_): _description_
            time_multiplier (int, optional): _description_. Defaults to 5.
        """
        self.notes = sorted(notes, key=lambda n: n[2])  # Sort by time
        self.time_multiplier = time_multiplier
        self.NoteData = self.compute_vectors()
        #print(self.vectors[0:500])

        self.patterns = []
        #self.classified_notes = set()

    def classify_patterns(self):
        NoteData = self.detect_sequences()
        return NoteData
        #return dict(self.patterns)

    def compute_vectors(self):
        """Compute the movement vectors between consecutive notes."""
        NoteData = [Note(note=self.notes[0], vector=None)]
        for i in range(1, len(self.notes)):
            x1, y1, t1 = self.notes[i-1]
            x2, y2, t2 = self.notes[i]
            vector = (abs(x2 - x1), abs(y2 - y1), abs(t2 - t1), round(math.hypot(abs(x2 - x1), abs(y2 - y1)), 2))# max((x2 - x1), abs(y2 - y1)))#  # |(dx, dy, dt, dxy)| = |(dx, dy, dt, math.sqrt((p*p)+(b*b)))|
            NoteClass = Note(note=self.notes[i], vector=vector)
            NoteData.append(NoteClass) # last one should always go up but if it doesnt then whatever

        return NoteData
    
    def last_ruleset(self, buffer, NoteData):
        # Check if all notes in the buffer have "jumpstream" classification
        all_spiral = all("spiral" in note.classifications for note, _ in buffer)
        #print(all_spiral)
        all_jumpstream = all("jumpstream" in note.classifications for note, _ in buffer)

        # Apply the rules for short-slide and medium-slide
        if all_spiral:
            buffer_length = len(buffer)
            
            if buffer_length <= 3:
                classification = "short-slide"
                #print("short slide")
            elif 4 <= buffer_length <= 5:
                classification = "medium-slide"
                #print("med slide")
            else:
                classification = None
            
            # If we determined a valid classification, update NoteData
            if classification:
                for note, index in buffer:
                    # Update the note classification in both buffer and NoteData
                    #note.classifications.append(classification)
                    #print(index)
                    NoteData[index].classifications.append(classification)

        # Return the updated NoteData
        return NoteData


    def detect_sequences(self, maxjumpcount=2, maxspiralcount=3):
        """
        Detect sequences of jumpstreams and spirals in NoteData.
        """

        # For anyone looking through this code. I feel terribly sorry for you.
        # Changing these parameters even slightly will completely change the output.
        # The setup currently works (somehow)
        # If you want to try and fix it, be my guest.

        NoteData = self.NoteData  # Notes and vectors
        #print(NoteData[0].dt)  # testing

        print(len(NoteData))

        i = 0
        buffer = []
        clearbuffer = False
        firstNoteSwitch = False
        while len(NoteData) > i:
            Note = None
            Note = NoteData[i] # easier ref
            #print(NoteData[i].dt, i)

            # Reset the classifications list for the current note to avoid duplicates
            Note.classifications = []

            # Classify the note based on its 'dh' value
            if Note.dh >= 1.4:  # if it's a jump
                if not firstNoteSwitch:
                    firstNoteSwitch = True
                    #NoteData = self.first_ruleset(buffer, NoteData)
                Note.classifications.append("jumpstream")
                clearbuffer = True
            elif Note.dh <= 1.4 and Note.dh > 0.1:
                if not firstNoteSwitch:
                    NoteData[i-1].classifications.insert(0, "spiral")
                    #NoteData = self.first_ruleset(buffer, NoteData)
                    firstNoteSwitch = True
                Note.classifications.append("spiral")                

            # misc values
            if Note.x > 2 or Note.x < 0 or Note.y > 2 or Note.y < 0:
                Note.classifications.append("offgrid")

            #print(Note.x, Note.x != round(Note.x))
            if Note.x != round(Note.x) or Note.y != round(Note.y):
                Note.classifications.append("quantum")

            if Note.dx < 0.1 and Note.dy < 0.1:
                if Note.dt < 5: # ms
                    if not firstNoteSwitch:
                        NoteData[i-1].classifications.append("meganote")
                        #NoteData = self.first_ruleset(buffer, NoteData)
                        firstNoteSwitch = True

                    Note.classifications.append("jumpstream") if "jumpstream" in NoteData[i-1].classifications else None
                    Note.classifications.append("spiral") if "spiral" in NoteData[i-1].classifications else None
                    Note.classifications.append("meganote")
                else:
                    if not firstNoteSwitch:
                        NoteData[i-1].classifications.append("stack")
                        #NoteData = self.first_ruleset(buffer, NoteData)
                        firstNoteSwitch = True

                    Note.classifications.append("jumpstream") if "jumpstream" in NoteData[i-1].classifications else None
                    Note.classifications.append("spiral") if "spiral" in NoteData[i-1].classifications else None
                    Note.classifications.append("stack") 
            
            # Must be last for last_ruleset
            if clearbuffer:
                NoteData = self.last_ruleset(buffer, NoteData)
                buffer = []
                clearbuffer = False
                firstNoteSwitch = False
            buffer.append((NoteData[i], i))

            i += 1

        self.NoteData = NoteData
        return NoteData

    """
    def get_pattern_prevalence(self):
        total_notes = sum(len(seq) for seqs in self.patterns.values() for seq in seqs)
        return {pattern: sum(len(seq) for seq in seqs) / total_notes 
                for pattern, seqs in self.patterns.items()}
    """
    
    def get_pattern_prevalence(self):
        """
        Calculate the prevalence of each pattern type in the detected patterns.
        """
        total_notes = sum(len(seq) for _, seq in self.patterns)
        
        if total_notes == 0:
            return {}  # No patterns to calculate prevalence for

        pattern_counts = {}
        for pattern, seq in self.patterns:
            if pattern not in pattern_counts:
                pattern_counts[pattern] = 0
            pattern_counts[pattern] += len(seq)

        # Normalize counts by the total number of notes
        prevalence = {pattern: count / total_notes for pattern, count in pattern_counts.items()}

        return prevalence

# Convert hex color to RGB
def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

# Convert RGB to hex
def rgb_to_hex(rgb_color):
    return '#{:02x}{:02x}{:02x}'.format(*rgb_color)

# Blend multiple colors by averaging their RGB values
def blend_colors(colors):
    rgb_colors = [hex_to_rgb(color) for color in colors]
    avg_rgb = [sum(x) // len(x) for x in zip(*rgb_colors)]
    return rgb_to_hex(tuple(avg_rgb))


if __name__ == "__main__":
    from pysspm_rhythia import read_sspm
    import math

    # Load the SSPM data
    
    beatmap = read_sspm(r"C:\Users\david\AppData\Roaming\SoundSpacePlus\maps\teft2oo_tn-shi_-_contradiction.sspm")

    # Instantiate the classifier
    classifier = NoteClassifier(beatmap.notes, time_multiplier=1)

    # Classify patterns
    patterns = classifier.classify_patterns()
    print("Detected Patterns:", len(patterns))

    # Write results to a file
    with open("./tests/classificationtest.txt", "w") as f:
        f.write("Detected Patterns with Notes:\n")
        for i, note in enumerate(patterns):
            f.write(f"{i}  {note.note}: {note.classifications}:\n")
            
        #f.write(f"Sequence length: {len(patterns)}\n")

        # Total patterns detected
        f.write(f"Total patterns detected: {len(patterns)}\n")

        # Prevalence of each pattern
        #prevalence = classifier.get_pattern_prevalence()
        #f.write(f"-----------------\nPrevalence: {prevalence}\n")
        #f.write(f"Length of Notes: {len(parser.Notes)}\n")

        # Pattern sequence lengths
        #f.write("Length of pattern notes: " + ", ".join([f"{pattern}: {len(set(seq))}" for pattern, seq in patterns]) + "\n")

    #rint("Prevalence:", prevalence)

    # Color settings and saving to file
    COLORS = {
        "vibro": "#FF0000", 
        "quantum": "#52EE6A", 
        "star": "#E300E3", 
        "jumpstream": "#FF00FF", 
        "slide": "#FFFF00", 
        "broken_spiral": "#00FF00", 
        "spiral": "#00FFFF",
        "complex": "#00FF00",
        "stack": "#00E355",
        "meganote": "#55E300",
        "offgrid": "#E35500",
        "short-slide": "#0055E3",
        "medium-slide": "#E355E3",
    }
    file = r"C:\Users\david\AppData\Roaming\SoundSpacePlus\colorsets\whatwedidinthedessertvisiontest.txt"

    # Write color-coded output to a file
    with open(file, 'a') as f:
        f.write("")
    with open(file, "w") as f:
        # Iterate over all notes
        for note in patterns:
            classifications = note.classifications
            if classifications:
                # Get all the corresponding colors for the classifications
                colors = [COLORS.get(classification, '#000000') for classification in classifications]
                # If there are multiple classifications, blend their colors
                if len(colors) > 1:
                    color = blend_colors(colors)
                else:
                    color = colors[0]  # Just use the first color if only one classification

                # Write the blended color to the file
                f.write(f"{color}\n")
