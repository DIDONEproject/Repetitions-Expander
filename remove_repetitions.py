import music21 as m21 
import os
import itertools
import copy
import pyfiglet
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
import time
import copy
file_names = []
repeat_bracket = False

def measure_ranges(instrument_measures, init, end, iteration=None, offset=None, twoCompasses=False, remove_repetition_marks = False):
    measures = []
    o = offset
    last_offset = 0.0 if int(init) - 6 < 0 else instrument_measures[int(init) - 6].offset

    #Find index where measureNumber init and end is stored
    init_index = instrument_measures.index([m for m in instrument_measures if m.measureNumber == init][0])
    end_compass = [m for m in instrument_measures if m.measureNumber == end]
    end_index = instrument_measures.index(end_compass[0]) if len(end_compass) > 0 else len(instrument_measures) - 1
    for i in range(init_index, end_index + 1):
        if not i < 0 and i < len(instrument_measures) and instrument_measures[i].measureNumber >= int(init) and instrument_measures[i].measureNumber <= int(end):
            if not twoCompasses:
                compass = instrument_measures[i].quarterLength
                m = m21.stream.Measure(number =instrument_measures[i].measureNumber)
                if remove_repetition_marks:
                    m.elements = [e for e in instrument_measures[i].elements if not isinstance(e, m21.repeat.RepeatMark)]
                else:
                    m.elements = instrument_measures[i].elements 
                m.quarterLength = compass
                if offset is None:
                    m.offset = last_offset
                else:
                    m.offset = o
                    o += compass
                
                measures.append(m)
                if instrument_measures[i].measureNumber is not 0.0 and instrument_measures[i].offset != 0:
                    last_offset = instrument_measures[i].offset + compass
            twoCompasses = False
    
    """if iteration is 1:
        measures = measures[:-1]
    elif iteration is 2:
        measures = measures[:-2] + [measures[-1]]"""
    if iteration is 2:
        last_measure = instrument_measures[i + 1]
        last_measure.offset = measures[-1].offset
        measures = measures[:-1] + [last_measure]
    return measures

def get_instrument_elements(part):
    measures = []
    for elem in part:
        if isinstance(elem, m21.stream.Measure):
            measures.append(elem)
            #Change the note offsets to avoid problems due to the slurs
            last_offset = 0
            last_duration = 0
            for note in elem:
                if isinstance(note, m21.note.Note) or isinstance(note, m21.note.Rest) or isinstance(note, m21.chord.Chord):
                    note.offset = last_offset + last_duration
                    last_offset = note.offset
                    last_duration = note.duration.quarterLength
    return measures

def get_repeat_elements(score):
    global repeat_bracket
    repeat_bracket = False
    # 1. Get the repeat elements
    repeat_elements = set()
    
    for instruments in score.parts:
        instr_repeat_elements = []
        for elem in instruments.elements:
            if isinstance(elem, m21.stream.Measure):
                for e in elem:
                    if isinstance(e, m21.repeat.RepeatMark) and not isinstance(e, m21.bar.Repeat):
                        measure = e.measureNumber
                        if elem.numberSuffix == 'X1': #Exception
                            measure += 1
                        instr_repeat_elements.append((measure, e.name))
            elif isinstance(elem, m21.spanner.RepeatBracket):
                repeat_bracket = True
                string_e = str(elem)
                index = string_e.find("music21.stream.Measure")
                string_e = string_e[index:].replace("music21.stream.Measure ", '')
                measure = string_e.split(' ')[0].strip().replace('X1', '')
                instr_repeat_elements.append((int(measure), "repeat bracket" + elem.number))
        repeat_elements.update(instr_repeat_elements)
    
    repeat_elements = sorted(list(repeat_elements), key=lambda tup:tup[0])
    print("The repeat elements found in this score are: " + str(repeat_elements))
    return repeat_elements

def expand_repeat_bars(score):
    final_score = m21.stream.Score()
    final_score.metadata = score.metadata
    exist_repetition_bars = False
    #find repeat bars and expand
    for instr in score.parts:
        part_measures = get_instrument_elements(instr.elements) #returns the measures with repetitions
        last_measure = part_measures[-1].measureNumber
        part_measures_expanded = []
        startsin0 = part_measures[0].measureNumber is 0 #Everything should be -1
        repetition_bars = []

        #Find all repetitions in that instrument
        for elem in instr.elements:
            if isinstance(elem, m21.stream.Measure):
                for e in elem:
                    if isinstance(e, m21.bar.Repeat):
                        exist_repetition_bars = True
                        if e.direction == "start":
                            repetition_bars.append((e.measureNumber, "start"))
                        elif e.direction == "end":
                            repetition_bars.append((e.measureNumber, "end"))
                        index = elem.elements.index(e)
                        elem.elements = elem.elements[:index] + elem.elements[index + 1:]
            elif isinstance(elem, m21.spanner.RepeatBracket):
                string_e = str(elem)
                index = string_e.find("music21.stream.Measure")
                measure = string_e[index:].replace("music21.stream.Measure", '')[1:3].strip()
                repetition_bars.append((int(measure), elem.number))
                index = instr.elements.index(elem)
                elem.elements = instr.elements[:index] + instr.elements[index + 1:]
        repetition_bars = sorted(list(repetition_bars), key=lambda tup:tup[0])

        start = 0 if startsin0 else 1
        if exist_repetition_bars:
            p = m21.stream.Part()
            p.id = instr.id
            p.partName = instr.partName
            for rb in repetition_bars:
                compass = measure_ranges(part_measures, rb[0], rb[0])[0].quarterLength
                if rb[1] == "start":
                    if len(part_measures_expanded) > 0:
                        offset = part_measures_expanded[-1][-1].offset
                    else:
                        offset = 0
                    start_measures = measure_ranges(part_measures, start, rb[0] - 1, offset = offset + compass) #TODO works if the score doesn't start in 0?
                    if len(start_measures) > 0:
                        part_measures_expanded.append(start_measures)
                    start = rb[0]
                elif rb[1] == "end":
                    if len(part_measures_expanded) > 0:
                        offset = part_measures_expanded[-1][-1].offset
                    else:
                        offset = 0
                    casilla_1 = True if any(re[1] == '1' and re[0] <= rb[0] for re in repetition_bars) else False
                    casilla_2 = None
                    if casilla_1:
                        casilla_2 = [re for re in repetition_bars if re[1] == '2' and re[0] > rb[0]]
                        casilla_2 = None if len(casilla_2) is 0 else casilla_2[0] 
                    part_measures_expanded.append(measure_ranges(part_measures, init = start, end = rb[0], offset = offset+ compass, remove_repetition_marks=True)) # This should erase the repetition marks
                    if casilla_2 is not None:
                        part_measures_expanded.append(measure_ranges(part_measures, start, casilla_2[0], iteration = 2, offset = part_measures_expanded[-1][-1].offset+ compass))
                        start = casilla_2[0] + 1
                    else:
                        part_measures_expanded.append(measure_ranges(part_measures, init = start, end = rb[0], offset = part_measures_expanded[-1][-1].offset + compass))
                        start = rb[0] + 1
            if start < last_measure:
                compass = measure_ranges(part_measures, start, start + 1)[0].quarterLength
                offset = part_measures_expanded[-1][-1].offset
                part_measures_expanded.append(measure_ranges(part_measures, start, last_measure + 1, offset = offset+ compass)) #TODO works when it's close to the end?

            p.elements = list(itertools.chain(*tuple(part_measures_expanded)))
            final_score.insert(0, p)
        
    return final_score if exist_repetition_bars else score

def get_measure_list(part_measures, repeat_elements):
    measures_list = []
    startsin0 = part_measures[0].measureNumber is 0 #Everything should be -1

    there_is_fine = False
    there_is_segno = False
    #1. find the fine and segno
    if any([r[1] == "fine" for r in repeat_elements]):
        f = [x[0] for x in repeat_elements if x[1] == "fine"][0]
        there_is_fine = True
    if any([r[1] == "segno" for r in repeat_elements]):
        s = [x[0] for x in repeat_elements if x[1] == "segno"][0]
        there_is_segno = True

    #2. Having all the repetition elements, get the measures
    if there_is_segno: #Introduction
        before_segno = measure_ranges(part_measures,1 if not startsin0 else 0, s - 1)
        measures_list.append(before_segno) #S -1 OR S-> when segno in compass 1, s, else s-1?
        dc_time_signature = [y for x in before_segno for y in x.elements if isinstance(y, m21.meter.TimeSignature)]
    elif there_is_fine:
        measures_list.append(measure_ranges(part_measures,1 if not startsin0 else 0, f - 1, iteration = 1 if repeat_bracket else None))
    else:
        measures_list.append(measure_ranges(part_measures,1 if not startsin0 else 0, len(part_measures), iteration = 1 if repeat_bracket else None))

    for repeat in repeat_elements:
        repeat_measure = measure_ranges(part_measures, repeat[0], repeat[0])
        compass = repeat_measure[0].quarterLength

        if repeat[1] == "segno":
            offset = measures_list[-1][-1].offset
            segno_part = measure_ranges(part_measures, s, f - 1 if there_is_fine else len(part_measures), iteration = 1 if repeat_bracket else None, offset = offset + compass, remove_repetition_marks = True)
            measures_list.append(segno_part) # Segno to Fine
        elif repeat[1] == "fine":
            twoCompasses = False
            """if len(repeat_measure) > 0:
                twoCompasses = True"""
            offset = measures_list[-1][-1].offset
            fine_part = measure_ranges(part_measures, f, len(part_measures), offset = offset + compass, twoCompasses=twoCompasses, remove_repetition_marks = True)
            measures_list.append(fine_part) # Fine to end
        elif repeat[1] == "al segno" or repeat[1] == "dal segno":
            offset = measures_list[-1][-1].offset
            # segnos' compass time signature
            segno_time_measure = [x for x in segno_part[0].elements if isinstance(x, m21.meter.TimeSignature)]
            segno_time_measure = segno_time_measure if len(segno_time_measure) != 0 else dc_time_signature[-1]
            alsegno_list = measure_ranges(part_measures, s, f - 1 if there_is_fine else len(part_measures), iteration = 2 if repeat_bracket else None, offset=offset + compass, remove_repetition_marks = True)
            if not any(isinstance(x, m21.meter.TimeSignature) for x in alsegno_list[0].elements):
                #we reset the time signature that was on the dacapo
                alsegno_list[0].elements = tuple([segno_time_measure] + list(alsegno_list[0].elements))
            
            measures_list.append(alsegno_list) # Segno to fine
        elif repeat[1] == "da capo":
            offset = measures_list[-1][-1].offset
            if startsin0 and there_is_fine and not repeat_bracket:
                f += 1
            dacapo_list = measure_ranges(part_measures, 0 if startsin0 else 1, f - 1 if there_is_fine else len(part_measures), iteration = 2 if repeat_bracket else None, offset=offset + compass, remove_repetition_marks = True)
            measures_list.append(dacapo_list)

    return measures_list

def slur_processing(part):
    slurs = [s for s in part.elements if isinstance(s, m21.spanner.Slur)]
    part_measures = get_instrument_elements(part.elements) #returns the measures with repetitions

    for slur in slurs:
        slur_notes = slur.getSpannedElements()
        first_note_measure = slur_notes[0].measureNumber
        first_note_offset = slur_notes[0].offset
        last_note_measure = slur_notes[-1].measureNumber
        last_note_offset = slur_notes[-1].offset
        #Buscar ese compas y offset y recorrer desde esa nota hasta la siguiente
        implied_measures = measure_ranges(part_measures, first_note_measure, last_note_measure)
        first_found = False
        last_found = False
        for measure in implied_measures:
            notes = measure.elements
            i = 0
            while i < len(notes) and not last_found:
                if isinstance(notes[i], m21.note.Note):
                    if notes[i].offset == first_note_offset:
                        first_found = True
                    elif notes[i].offset == last_note_offset:
                        last_found = True
                    elif first_found and not last_found:
                        slur.addSpannedElements(notes[i])
                i += 1

def expand_score_repetitions(score, repeat_elements):
    score = expand_repeat_bars(score) # FIRST EXPAND REPEAT BARS
    final_score = m21.stream.Score()
    final_score.metadata = score.metadata
    
    if len(repeat_elements) > 0:
        for part in score.parts:
            part_measures = get_instrument_elements(part.elements) #returns the measures with repetitions
            p = m21.stream.Part()
            p.id = part.id
            p.partName = part.partName
            
            part_measures_expanded = get_measure_list(part_measures, repeat_elements) #returns the measures expanded
            part_measures_expanded = list(itertools.chain(*part_measures_expanded))
            #part_measures_expanded = sorted(tuple(part_measures_expanded), key =lambda x: x.offset)
            # Assign a new continuous compass number to every measure
            measure_number = 0 if part_measures_expanded[0].measureNumber == 0 else 1
            for i, e in enumerate(part_measures_expanded):
                m = m21.stream.Measure(number = measure_number)
                m.elements = e.elements
                m.offset  = e.offset
                m.quarterLength = e.quarterLength
                part_measures_expanded[i] = m
                measure_number += 1
            p.elements = part_measures_expanded

            final_score.insert(0, p)
    else:
        final_score = score
    return final_score

def file_dialog(root, file_formats, final_dir):
    file_names = filedialog.askopenfilenames(parent = root, initialdir=os.getcwd(), title='Choose one or more files', filetypes = file_formats, multiple = True)
    print("FILES CHOOSED: ", file_names) 
    
    progress = ttk.Progressbar(root, orient = tk.HORIZONTAL, length = 100, mode = "determinate", maximum=len(file_names))
    progress.pack()
    root.update()
    
    if not os.path.isdir(final_dir):
        os.mkdir(final_dir)

    #chivato = open(os.getcwd()+"/chivato_dcAnacrusa.txt", "a")
    if len(file_names) != 0:
        for index, score_path in enumerate(file_names):
            index += 1
            if score_path[-3:] == 'xml' or score_path[-3:] == 'mxl':
                print('\n', str(index) + '/' + str(len(file_names)) + " ########################################")
                print("Working with " + score_path)
                score = m21.converter.parse(score_path)
                repeat_elements = get_repeat_elements(score) #returns all the existing repeat elements (only in the first voice)
                """if any(r[1] == 'da capo' for r in repeat_elements) and any(e.measureNumber == 0 for p in score.parts for e in p.elements):
                    chivato.write(score_path + '\n')
                    print("Me voy a chivar!")"""
                final_score = expand_score_repetitions(score, repeat_elements)
                score_name = score_path.split('/')[-1]
                final_score.write('xml', os.getcwd() + "\\SCORESEXPANDED\\"+ score_name[:-4]+".xml")
                print("Expanded version stored in : ", os.getcwd() + "\\SCORESEXPANDED\\"+ score_name[:-4]+".xml")
            progress['value'] = index
            root.update()
    time.sleep(2)
    #chivato.close()
    root.destroy()

if __name__ == "__main__":
    file_formats = [("MusicXML", ".xml"), ("Compressed MusicXML", ".mxl")]
    print(pyfiglet.figlet_format("Repetitions Expander", font = "banner3-D", width=120 ))
    print(pyfiglet.figlet_format("Didone Project", font = "banner3-D", width=200 ))
    print("Initiating repetitions expander...")
    print("This program takes a xml score and returns an xml in the current working directory /SCORESEXPANDED")
    print("Warning: This program doesn't maintain the slurs (by the moment)")
    final_dir = os.getcwd() + "/SCORESEXPANDED"
    opera = '_'
    aria_name = '_'
    list_operas = []
    chooser = tk.Tk()
    chooser.title("Repetitions expander")
    chooser.geometry('300x150')
    label = tk.Label(chooser, text="Welcome to the repetition expander. \n Please, choose several XML or MXL files to expand.")
    label.pack()
    button = tk.Button(chooser, text= "Browse", command = lambda: file_dialog(chooser, file_formats, final_dir))
    button.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
    button.pack(pady = 10)
    chooser.mainloop()