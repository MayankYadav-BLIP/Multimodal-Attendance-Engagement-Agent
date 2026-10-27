import threading
import time
import numpy as np
import sounddevice as sd


class AudioMonitor:
    def __init__(self, samplerate=16000, block_seconds=0.1, speech_factor=3.0,
                 min_level=0.01, hold_seconds=1.0):
        self.samplerate = samplerate
        self.block_size = int(samplerate * block_seconds)
        self.speech_factor = speech_factor  # how many times louder than background counts as speech
        self.min_level = min_level          # absolute minimum level to count as speech
        self.hold_seconds = hold_seconds    # keep "speaking" on this long after the last loud sound
        self.level = 0.0
        self.noise_floor = None
        self.last_loud = 0.0
        self._calib = []
        self._lock = threading.Lock()
        self.stream = None

    def _callback(self, indata, frames, time_info, status):
        rms = float(np.sqrt(np.mean(indata[:, 0] ** 2)))
        with self._lock:
            self.level = rms
            if self.noise_floor is None:
                self._calib.append(rms)
                if len(self._calib) >= 10:  # first ~1 second sets the background level
                    self.noise_floor = float(np.mean(self._calib))
                return
            threshold = max(self.noise_floor * self.speech_factor, self.min_level)
            if rms > threshold:
                self.last_loud = time.time()

    def start(self):
        self.stream = sd.InputStream(
            samplerate=self.samplerate,
            channels=1,
            blocksize=self.block_size,
            callback=self._callback,
        )
        self.stream.start()

    def stop(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()

    @property
    def calibrated(self):
        with self._lock:
            return self.noise_floor is not None

    @property
    def is_speaking(self):
        with self._lock:
            if self.noise_floor is None:
                return False
            return (time.time() - self.last_loud) < self.hold_seconds