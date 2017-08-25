import struct
import numpy as np
import pyaudio

from array import array
from sys import byteorder
from struct import pack
import wave
import cv2

import time
import os

nFFT = 512
BUF_SIZE = 4 * nFFT
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
FRAME_MAX_VALUE = 2 ** 15 - 1
NORMALIZE_MINUS_ONE_dB = 10 ** (-1.0 / 20)

DETECTION_LEVEL = 400 #this is important for the first calibration
                      #room voice level should be below this in order for it to calibrate properly
N_SILENT_PRE_CHUNK_TO_KEEP = 50
N_SILENT_CHUNK_TO_STOP = 50
MINIMUM_RECORDING_TIME_SECONDS = 2.5

DISPLAY = True
FIVE_MINUTES_SECONDS = 300

OUTPUT_FOLDER = './night_data'

#TODO : measure ambient level and remove it, then multiply signal for better sensitivity
#       IDEA : measure 20 max of chunk voice and take the min, that is the ambiant level

#       IDEAD : if bar drop to zero redo the ambiant calibration (microphone amplification varies up and down in time due to shitty sound card)

###################### IMAGE RELATED ###########################

class BgrColor():
    def __init__(self, b, g, r):
        """
        Represent a BLUE GREEN RED color
            - b : int for blue 0 - 255
            - g : int for green 0 - 255
            - r : int for red 0 - 255
        """
        self.b = b
        self.g = g
        self.r = r

class Point():
    def __init__(self, x, y):
        """
        Represent a point in a plan
            - x : x (on the width axis, 0 is at the left)
            - y : y (on the height axis, 0 is on the top)
        """
        self.x = int(x) #grer les float Nan
        self.y = int(y)

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        return 'src.models.Point : x=%s, y=%s' %(self.x, self.y)

class Line():
    def __init__(self, a, b):
        """
        Represent a plan
            - a : viewanalyser.Point, start of the line
            - b : viewanalyser.Point, end of the line
        """
        self.a = a
        self.b = b

    def __str__(self):
        return 'src.models.Line with points : a=%s, b=%s' %(self.a, self.b)

def drawLineOnPic(image, line, color, thickness):
    """
    Draw a line on an image, return nothing, send a the parameters copy for original keeping
        - image : a opencv image
        - line : a models.Line
        - color : a models.BgrColor, the line color
        - thickness : int representing the line thickness
    """
    cv2.line(image, (line.a.x, line.a.y), (line.b.x, line.b.y), (color.b, color.g, color.r,), thickness)

def createEmptyBgrBlackImage(width, height):
    """
    Create an empty black BGR opencv image
        - width : (int) representing the width
        - height : (int) representing the height
    """
    return np.zeros((height, width, 3), np.uint8)

def createEmptyBgrColoredImage(width, height, color):
    """
    Create an empty colored BGR opencv image
        - width : (int) representing the width
        - height : (int) representing the height
        - color : tuple((int), (int), (int)) - tuple containing BGR, 0 to 255 per value
    """
    im = np.zeros((height, width, 3), np.uint8)
    im[:] = color
    return im

def copyImageIntoOtherImage(bigImage, toCopy, upperLeftCoord):
    """
    paste an image inside an other, the original image is modified,
    use image.copy() before to save it if needed
        - bigImage : the opencv image where we are going to paste the small image
        - toCopy : the openCv image which is going to be pasted
        - upperLeftCoord : models.Point, uppe left coordinate where it's going to paste
    """
    bigImage[upperLeftCoord.y:toCopy.shape[0]+upperLeftCoord.y,
             upperLeftCoord.x:toCopy.shape[1]+upperLeftCoord.x] = toCopy

def makeVolumeBar(audio_volume, computed_detection_level):

    if audio_volume < 0:
        audio_volume = 0

    if audio_volume >= 1400:
        audio_volume = 1400

    bar_width, bar_height = 1400, 100
    volume_bar_img = createEmptyBgrBlackImage(bar_width, bar_height)
    if audio_volume>computed_detection_level:
        color = (0,255,0)
    else:
        color = (255,0,0)
    volumeIm = createEmptyBgrColoredImage(audio_volume, bar_height, color)
    copyImageIntoOtherImage(volume_bar_img, volumeIm, Point(0,0))
    drawLineOnPic(volume_bar_img, Line(Point(computed_detection_level, 0), Point(computed_detection_level, bar_height)), BgrColor(0,0,255), 3)
    return volume_bar_img

def draw_text(frame, text, x, y, color=(0,0,255), thickness=3, size=1,):
    if x is not None and y is not None:
        cv2.putText(
            frame, text, (int(x), int(y)), cv2.FONT_HERSHEY_SIMPLEX, size, color, thickness)

################################################ SOUND RELATED METHODS #######################################################

def normalize(data_all):
    """Amplify the volume out to max -1dB"""
    # MAXIMUM = 16384
    normalize_factor = (float(NORMALIZE_MINUS_ONE_dB * FRAME_MAX_VALUE)
                        / max(abs(i) for i in data_all))

    r = array('h')
    for i in data_all:
        r.append(int(i * normalize_factor))
    return r

def record_to_file(sample_width, data, path):
    "Records from the microphone and outputs the resulting data to 'path'"
    data = pack('<' + ('h' * len(data)), *data)

    wave_file = wave.open(path, 'wb')
    wave_file.setnchannels(CHANNELS)
    wave_file.setsampwidth(sample_width)
    wave_file.setframerate(RATE)
    wave_file.writeframes(data)
    wave_file.close()

def shiftLeft(l):
    return  l[1:]

def addToListAndShiftLeft(l, value):
    l = shiftLeft(l)
    l.append(value)
    return l

def getAverageValue(l):
    return int(float(sum(l)) / max(len(l), 1))

def read_available(stream):
    # Read n*nFFT frames from stream, n > 0
    n = max(stream.get_read_available() / nFFT, 1) * nFFT
    data = stream.read(n)
    return n, data

def computeVoiceLevelViaFFT(n, sound_data, MAX_y):
    """
    Compute the spectrum of what's coming in from the mic
    and only look at the 300-4000Hz part

    For example the 50Hz parasite were too high and were masking
    soft speak during detection

    With this there is no problem anymore
    """
    # Unpack data, LRLRLR...
    mic_data = np.array(struct.unpack("%dh" % (n * CHANNELS), sound_data)) / MAX_y
    mic_data_fft_complex = np.fft.fft(mic_data, nFFT)

    # Sewing FFT of two channels together, DC part uses right channel's
    int_fft = abs(mic_data_fft_complex[:nFFT / 2])
    #8 a 102 [39;06Hz par paqeut)
    HzPerStep = 20000/len(int_fft)
    Hz300 = 300/HzPerStep
    Hz4000 = 4000/HzPerStep
    FFT_human_voice_only = int_fft[Hz300:Hz4000]
    unfiltered_level = max(int_fft)
    voice_level = max(FFT_human_voice_only)
    return int(unfiltered_level*1000), int(voice_level*1000)

def measure_ambiant(stream):

    threshold = DETECTION_LEVEL

    print "measuring ambiant sound level"

    measurments = []
    for _ in range(100):
        n, sound_data = read_available(stream)
        _, instant_voice_level = computeVoiceLevelViaFFT(n, sound_data, MAX_y)

        if instant_voice_level>threshold: #someone started speaking, cancel ambiant calibration
            print "SOMEONE SPOKE DAMMNIT!!! cancelling ambiant noise calibration..."
            return None

        measurments.append(instant_voice_level)

    current_ambiant_level = getAverageValue(measurments)

    new_levels = []
    for level in measurments:
        level = level - current_ambiant_level
        if level < 0:
            new_levels.append(0)
        else:
            new_levels.append(level)
    average_level = getAverageValue(new_levels)

    new_threshold = int(average_level*13) #setting threshold to 20% higher than the ambiant level
    print "ambiant sound level is {}".format(current_ambiant_level)
    print "new threshold is {}".format(new_threshold)

    return current_ambiant_level, new_threshold

def recalibrate_for_ambiant_noise(stream):

    if DISPLAY:
        thisfilepath = os.path.realpath(__file__)
        base = os.path.split(thisfilepath)[0]
        firstim = cv2.imread(os.path.join(base, "ims/call001.jpg"))
        secondim = cv2.imread(os.path.join(base, "ims/call002.jpg"))
        cv2.imshow("volume", firstim)
        cv2.waitKey(1) # this block the execution for 1ms :(

    ambiant_results = measure_ambiant(stream)
    counter = 0
    while ambiant_results is None:
        counter = counter + 1
        if DISPLAY:
            to_display = secondim.copy()
            draw_text(to_display, str(counter).zfill(5), 670, 267)
            cv2.imshow("volume", to_display)
            cv2.waitKey(1) # this block the execution for 1ms :(
        ambiant_results = measure_ambiant(stream)

    return ambiant_results


p = pyaudio.PyAudio()

stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=BUF_SIZE)

MAX_y = 2.0 ** (p.get_sample_size(FORMAT) * 8 - 1)
voice_sound_levels = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
unfiltered_sound_levels = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

recording_chunks = []
currently_recording = False
silent_blocks = 0
pre_recording_silent_chunks = []
recording_number = 0
if DISPLAY:
    cv2.namedWindow("volume")

print "Starting 1st calibration..."
ambiant_volume_level, computed_detection_level = recalibrate_for_ambiant_noise(stream)
print "cliration completed"
silence_start_time = time.time()
recording_start_time = None
while True:

    if silence_start_time is not None:
        current_silence_duration_seconds = time.time() - silence_start_time
        print "Mic is sensing silence since : {} ms".format(current_silence_duration_seconds)
        if current_silence_duration_seconds >= FIVE_MINUTES_SECONDS:
            ambiant_volume_level, computed_detection_level = recalibrate_for_ambiant_noise(stream)

    if recording_start_time is not None:
        current_recording_duration_seconds = time.time() - recording_start_time
        print "Mic is sensing sound since : {} ms".format(current_recording_duration_seconds)
        if current_recording_duration_seconds >= FIVE_MINUTES_SECONDS:
            ambiant_volume_level, computed_detection_level = recalibrate_for_ambiant_noise(stream)

    n, sound_data = read_available(stream)
    unfiltered_inst_sound_level, voice_inst_sound_level = computeVoiceLevelViaFFT(n, sound_data, MAX_y)

    voice_sound_levels = addToListAndShiftLeft(voice_sound_levels, voice_inst_sound_level)
    unfiltered_sound_levels = addToListAndShiftLeft(unfiltered_sound_levels, unfiltered_inst_sound_level)

    average_unfiltered_level = getAverageValue(unfiltered_sound_levels)
    average_voice_level = getAverageValue(voice_sound_levels)

    average_unfiltered_level_no_ambiant = average_unfiltered_level-ambiant_volume_level
    average_voice_level_no_ambiant = average_voice_level-ambiant_volume_level

    average_voice_leve_no_ambiantl_amped = average_voice_level_no_ambiant*10

    if DISPLAY:
        unfiltered_volbar = makeVolumeBar(average_unfiltered_level_no_ambiant, computed_detection_level)
        clean_voice_volbar = makeVolumeBar(average_voice_leve_no_ambiantl_amped, computed_detection_level)
        bigim = createEmptyBgrBlackImage(1400, 300)
        copyImageIntoOtherImage(bigim, unfiltered_volbar, Point(0,33))
        copyImageIntoOtherImage(bigim, clean_voice_volbar, Point(0,166))
        cv2.imshow("volume", bigim)
        cv2.waitKey(1) # this block the execution for 1ms :(

    #prepare data for wav storage
    data_chunk = array('h', sound_data)
    if byteorder == 'big':
        data_chunk.byteswap()

    voice_detected = average_voice_leve_no_ambiantl_amped>computed_detection_level
    if voice_detected:
        if not currently_recording:
            print "start recording"
            recording_number = recording_number + 1
            recording_start_time = time.time()
            silence_start_time = None
        currently_recording = True
        silent_blocks = 0

    #we keep some of the pre-recording chunk, because detection oftend occurs 0.1-0.5 seconds
    #after speech started, adding those to the recording afterwards feels more natural
    if not currently_recording:
        if len(pre_recording_silent_chunks) >= N_SILENT_PRE_CHUNK_TO_KEEP:
            pre_recording_silent_chunks = shiftLeft(pre_recording_silent_chunks)
        pre_recording_silent_chunks.append(data_chunk)

    if currently_recording:

        recording_chunks.append(data_chunk)

        if not voice_detected:
            silent_blocks = silent_blocks+1
        if silent_blocks > N_SILENT_CHUNK_TO_STOP:
            #IF recording time < 2 seconds : discard
            record_lasted_seconds = time.time() - recording_start_time
            if record_lasted_seconds > MINIMUM_RECORDING_TIME_SECONDS:
                print "recording end - saving"
                #Add pre silent chunk before saving
                to_save = array('h')
                for chunk in pre_recording_silent_chunks:
                    to_save.extend(chunk)
                #Add recording data but remove the trailing 3 seconds of silences
                for i, chunk in enumerate(recording_chunks):
                    if i<len(recording_chunks)-N_SILENT_CHUNK_TO_STOP+5: #remove the 45 traiing silent chunk
                        to_save.extend(chunk)

                recording_name = str(recording_number).zfill(6)
                to_save = normalize(to_save)
                record_to_file(p.get_sample_size(FORMAT), to_save, 'recording{}.wav'.format(recording_name))
            else:
                print "recording end - false detection, disgarding"

            recording_start_time = None
            silence_start_time = time.time()
            currently_recording = False
            silent_blocks = 0
            recording_chunks = []
