import numpy as np
import logging

# Set up logging for VAD
logger = logging.getLogger(__name__)

class VoiceActivityDetector:
    def __init__(self, sample_rate, chunk_size, window_duration=1.0,
                 silence_ratio=1.5, min_speech_duration=0.3, min_silence_duration=1.0):
        """
        Initialize the Voice Activity Detector (VAD).

        :param sample_rate: Sampling rate of the audio stream.
        :param chunk_size: Number of frames per audio chunk.
        :param window_duration: Duration (in seconds) for noise RMS estimation.
        :param silence_ratio: Multiplier for noise RMS to set dynamic threshold.
        :param min_speech_duration: Minimum duration (in seconds) to consider as speech.
        :param min_silence_duration: Minimum duration (in seconds) to consider as silence.
        """
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.window_size = int(window_duration * sample_rate / chunk_size)
        self.silence_ratio = silence_ratio
        self.min_speech_frames = int(min_speech_duration * sample_rate / chunk_size)
        self.min_silence_frames = int(min_silence_duration * sample_rate / chunk_size)
        
        self.noise_rms_history = []
        self.dynamic_threshold = None
        self.is_speech = False
        self.speech_counter = 0
        self.silence_counter = 0

    def calculate_rms(self, audio_data):
        """
        Calculate Root Mean Square (RMS) of the audio data.

        :param audio_data: Numpy array of audio samples.
        :return: RMS value.
        """
        # Ensure audio_data is a NumPy array of type float
        audio_data = np.array(audio_data, dtype=np.float32)
        
        # Replace NaNs and Infs with 0
        if not np.isfinite(audio_data).all():
            logger.warning("Audio data contains NaN or Inf. Replacing with zeros.")
            audio_data = np.nan_to_num(audio_data)
        
        # Calculate RMS with a small epsilon to prevent sqrt(0)
        mean_sq = np.mean(np.square(audio_data))
        
        # Handle cases where mean_sq might be negative due to numerical errors
        if mean_sq < 0:
            logger.warning(f"Mean square is negative ({mean_sq}). Setting to zero.")
            mean_sq = 0.0
        
        rms = np.sqrt(mean_sq + 1e-10)
        return rms

    def update_noise_rms(self, rms):
        """
        Update the noise RMS history and calculate dynamic threshold.

        :param rms: Current RMS value.
        """
        if len(self.noise_rms_history) < self.window_size:
            self.noise_rms_history.append(rms)
        else:
            self.noise_rms_history.pop(0)
            self.noise_rms_history.append(rms)
        
        if len(self.noise_rms_history) == self.window_size:
            noise_rms = np.mean(self.noise_rms_history)
            self.dynamic_threshold = noise_rms * self.silence_ratio
            logger.debug(f"Updated dynamic_threshold: {self.dynamic_threshold:.4f}")

    def is_speech_frame(self, rms):
        """
        Determine if the current frame contains speech.

        :param rms: Current RMS value.
        :return: Boolean indicating speech presence.
        """
        if self.dynamic_threshold is None:
            return False
        return rms > self.dynamic_threshold

    def process_audio_chunk(self, audio_data):
        """
        Process an audio chunk to detect speech activity.

        :param audio_data: Numpy array of audio samples.
        :return: Tuple (speech_detected, is_speech)
        """
        rms = self.calculate_rms(audio_data)
        
        # Update noise RMS during initial phase
        if len(self.noise_rms_history) < self.window_size:
            self.update_noise_rms(rms)
            logger.debug(f"Noise RMS updated: {rms:.4f}")
            return (False, self.is_speech)

        speech = self.is_speech_frame(rms)
        
        if speech:
            self.speech_counter += 1
            self.silence_counter = 0
            if not self.is_speech and self.speech_counter >= self.min_speech_frames:
                self.is_speech = True
                self.speech_counter = 0
                logger.info("Speech started")
                return (True, self.is_speech)
        else:
            self.silence_counter += 1
            self.speech_counter = 0
            if self.is_speech and self.silence_counter >= self.min_silence_frames:
                self.is_speech = False
                self.silence_counter = 0
                logger.info("Speech ended")
                return (True, self.is_speech)

        return (False, self.is_speech)

    def reset(self):
        """Reset the VAD state."""
        self.noise_rms_history.clear()
        self.dynamic_threshold = None
        self.is_speech = False
        self.speech_counter = 0
        self.silence_counter = 0
        logger.info("VAD state reset")