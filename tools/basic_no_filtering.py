#taken from http://stackoverflow.com/questions/892199/detect-record-audio-in-python
#Added :
#
# - record non stop and make a file for each "session"
# - make an average of the sound level to remove spikes
# - display bar in console
#
# TODO
#
# - filter unwznted fresuency, noise from 50Hz (regular electricity) is too high too allow detection
#   of soft speak


from array import array
from struct import pack
from sys import byteorder
import struct

from models import SoundLevelTracker
from scipy import signal

import copy
import pyaudio
import wave
import numpy

THRESHOLD = 300  # audio levels not normalised.
CHUNK_SIZE = 1024
SILENT_CHUNKS = 3 * 44100 / CHUNK_SIZE  # about 3sec
FORMAT = pyaudio.paInt16
FRAME_MAX_VALUE = 2 ** 15 - 1
NORMALIZE_MINUS_ONE_dB = 10 ** (-1.0 / 20)
RATE = 44100
CHANNELS = 1
TRIM_APPEND = RATE / 4

def design_filter(lowcut, highcut, sampling_rate, order=3):
    nyq = 0.5*sampling_rate
    low = lowcut/nyq
    high = highcut/nyq
    b, a = signal.butter(order, [low,high], btype='band')
    return b, a

def normalize(data_all):
    """Amplify the volume out to max -1dB"""
    # MAXIMUM = 16384
    normalize_factor = (float(NORMALIZE_MINUS_ONE_dB * FRAME_MAX_VALUE)
                        / max(abs(i) for i in data_all))

    r = array('h')
    for i in data_all:
        r.append(int(i * normalize_factor))
    return r

def trim(data_all):
    _from = 0
    _to = len(data_all) - 1
    for i, b in enumerate(data_all):
        if abs(b) > THRESHOLD:
            _from = max(0, i - TRIM_APPEND)
            break

    for i, b in enumerate(reversed(data_all)):
        if abs(b) > THRESHOLD:
            _to = min(len(data_all) - 1, len(data_all) - 1 - i + TRIM_APPEND)
            break

    return copy.deepcopy(data_all[_from:(_to + 1)])

def record(soundLevelTracker):
    """Record a word or words from the microphone and 
    return the data as an array of signed shorts."""
    
    # design the filter
    b,a = design_filter(300, 4500, RATE, 3)
    # compute the initial conditions.
    if soundLevelTracker.lastFilterZi is None:
        soundLevelTracker.lastFilterZi = signal.lfilter_zi(b, a)

    pyAudio = pyaudio.PyAudio()
    stream = pyAudio.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, output=True, frames_per_buffer=CHUNK_SIZE)

    silent_chunks = 0
    audio_started = False
    data_all = array('h') #Represents signed integer of size 2 bytes, ex of representation -< array('h', [0, 0, -1, 0, 0, 0, 0, 0]

    while True:
        #print "recording chunk"
        # little endian, signed short
        chunk_as_string = stream.read(CHUNK_SIZE)
        
        #Convert from stream of bytes to a list of short integers (2 bytes here) in "samples":
        #shorts = (struct.unpack( "128h", data ))
        shorts = (struct.unpack( 'h' * CHUNK_SIZE, chunk_as_string));
        chunk_for_filter = numpy.array(list(shorts),dtype=float);
        print chunk_for_filter

        data_chunk = array('h', chunk_as_string)
        if byteorder == 'big':
            data_chunk.byteswap()
        data_all.extend(data_chunk)
        
        
        
        soundLevelTracker.add_to_sound_history(max(data_chunk))
        silent = soundLevelTracker.is_silent()

        soundLevelTracker.printHihestVolume()
        soundLevelTracker.printAudioBar()
        
        if audio_started:
            #print "WE ARE CURRENTLY RECORDING"
            if silent:
                silent_chunks += 1
                if silent_chunks > SILENT_CHUNKS:
                    break
            else: 
                silent_chunks = 0
        elif not silent:
            audio_started = True

    sample_width = pyAudio.get_sample_size(FORMAT)
    stream.stop_stream()
    stream.close()
    pyAudio.terminate()

    data_all = trim(data_all)  # we trim before normalize as threshhold applies to un-normalized wave (as well as is_silent() function)
    data_all = normalize(data_all)
    return sample_width, data_all

def record_to_file(soundLevelTracker, filename):
    "Records from the microphone and outputs the resulting data to 'filename'"
    sample_width, data = record(soundLevelTracker)
    data = pack('<' + ('h' * len(data)), *data)

    wave_file = wave.open(filename, 'wb')
    wave_file.setnchannels(CHANNELS)
    wave_file.setsampwidth(sample_width)
    wave_file.setframerate(RATE)
    wave_file.writeframes(data)
    wave_file.close()

if __name__ == '__main__':
    print "recording has started, listening and storing voices"
    print "recording are stored after 3 seconds of silence then a new one start when there is sound"
    print "good night"
    soundLevelTracker = SoundLevelTracker(THRESHOLD)
    counter = 1
    while True:
        record_to_file(soundLevelTracker, 'recording{}.wav'.format(str(counter).zfill(5)))
        counter = counter + 1
