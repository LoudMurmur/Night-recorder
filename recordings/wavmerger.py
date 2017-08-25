import wave
import os

from os import listdir
from os.path import isfile, join

infiles = [ f for f in listdir(".") if isfile(join(".",f)) and 'desktop.ini' not in f ]
outfile = "thisNight.wav"

data= []
for infile in infiles:
    if os.path.splitext(infile)[1] == ".wav":
        w = wave.open(infile, 'rb')
        print "reading {}".format(infile)
        data.append( [w.getparams(), w.readframes(w.getnframes())] )
        w.close()

print "writing big wav"
output = wave.open(outfile, 'wb')
output.setparams(data[0][0])
for params,frames in data:
    output.writeframes(frames)
output.close()