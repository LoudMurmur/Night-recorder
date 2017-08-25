# Night-recorder #

This is not just a basic recorder!!!!

it will :

 * calibrate by itself according to ambiant noise
 * listen only for humain voice, yup it does filtering on the sound
 * make 1 file per recording
 * normalize each recording (it amplify the sound sample to it's max without saturation)
 * recalibrate ambiant noise trigger if there is too much silence/sound after some time
 
### How to use ? ###

You need python, the opencv python stuff, scipy, numpy, you'll see
from the first stacktrace when running it :p

 * run night_recorder.py to start the recorder
 * recordings go into /recordings
 
Simple right?

plus : in recordings there is wavmerger.py, run it and it will merge all your recordings into one

### Your code is dirty ###

This is an old project I found whil cleaning my HDDs, don't judge!
It's awesome tho.

### what does it look like? ###

![it look like this](/ims/ex.png?raw=true "it look like this")

### by the way ###

Don't look in the tools folder -_-
