
class SoundLevelTracker:
    
    def __init__(self, silence_threshold):
        self.sound_volume_history = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        self.highest_level = 0
        self.highest_counter = 0
        self.silent_threshold = silence_threshold
        self.lastFilterZi = None

    def is_average_array_ready(self):
        if 0 in self.sound_volume_history:
            return False
        return True

    def add_to_sound_history(self, audioVolume):
        #audio volume is max(data_chunk)
        

        self.sound_volume_history = self.sound_volume_history[1:]
        self.sound_volume_history.append(audioVolume)
        
        avgVolume = self.compute_current_average_audio_volume()
        if avgVolume>self.highest_level:
            self.highest_level = avgVolume
            
        self.highest_counter = self.highest_counter + 1
        if self.highest_counter > 100:
            self.highest_counter= 0
            self.highest_level = 0
        
    def compute_current_average_audio_volume(self):
        return int(float(sum(self.sound_volume_history))/len(self.sound_volume_history))
    
    def is_silent(self):
        
        #print "current average volume is {}".format(self.compute_current_average_audio_volume())
        
        if not self.is_average_array_ready():
            return True
        
        if self.compute_current_average_audio_volume() < self.silent_threshold:
            return True
        return False
    
    
    def printHihestVolume(self):
        pass
        #print "highest recorded sound volume for the last 100 chunk : {}".format(self.highest_level)
        
    def printAudioBar(self):
        numberOfStepInBar = int(self.compute_current_average_audio_volume()/10)
        displayedBar = ""
        for i in range(numberOfStepInBar):
            if i<= self.silent_threshold/10:
                displayedBar = displayedBar + "#"
            else:
                displayedBar = displayedBar + "[]"
            
        print displayedBar
