import logging
import pyaudio
import numpy as np
import queue
import threading
import time
import wave

# Constants for PyAudio Configuration
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 24000  # Default sample rate
FRAMES_PER_BUFFER = 1024

logger = logging.getLogger(__name__)


class AudioPlayer:
    """Handles audio playback for decoded audio data using PyAudio."""

    def __init__(self, min_buffer_fill=3, max_buffer_size=0, enable_wave_capture=False):
        """
        Initializes the AudioPlayer with a pre-fetch buffer threshold.

        :param min_buffer_fill: Minimum number of buffers that should be filled before starting playback initially.
        :param max_buffer_size: Maximum size of the buffer queue.
        """
        self.initial_min_buffer_fill = min_buffer_fill
        self.min_buffer_fill = min_buffer_fill
        self.buffer = queue.Queue(maxsize=max_buffer_size)
        self.pyaudio_instance = pyaudio.PyAudio()
        self.stream = None
        self.stop_event = threading.Event()
        self.reset_event = threading.Event()
        self.playback_complete_event = threading.Event()
        self.buffer_lock = threading.Lock()
        self.enable_wave_capture = enable_wave_capture
        self.wave_file = None
        self.buffers_played = 0

        # Fade-out related attributes
        self.fade_out_event = threading.Event()
        self.fade_out_duration = 100  # in milliseconds
        self.fade_volume = 1.0
        self.fade_step = 0.0
        self.total_fade_steps = 0

        self._initialize_wave_file()
        self._initialize_stream()
        self._start_thread()

    def _initialize_wave_file(self):
        if self.enable_wave_capture:
            try:
                self.wave_file = wave.open("playback_output.wav", "wb")
                self.wave_file.setnchannels(CHANNELS)
                self.wave_file.setsampwidth(self.pyaudio_instance.get_sample_size(FORMAT))
                self.wave_file.setframerate(RATE)
                logger.info("Wave file for playback capture initialized.")
            except Exception as e:
                logger.error(f"Error opening wave file for playback capture: {e}")

    def _initialize_stream(self):
        """Initializes or reinitializes the PyAudio stream."""
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.stream = self.pyaudio_instance.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            output=True,
            frames_per_buffer=FRAMES_PER_BUFFER
        )
        logger.info("PyAudio stream initialized.")

    def _start_thread(self):
        """Starts the playback thread."""
        self.thread = threading.Thread(target=self.playback_loop, daemon=True)
        self.thread.start()
        logger.info("Playback thread started.")

    def is_audio_playing(self):
        """Checks if audio is currently playing."""
        with self.buffer_lock:
            buffer_not_empty = not self.buffer.empty()
        is_playing = buffer_not_empty
        logger.debug(f"Checking if audio is playing: Buffer not empty = {buffer_not_empty}, "
                     f"Is playing = {is_playing}")
        return is_playing

    def playback_loop(self):
        """Main playback loop that handles audio streaming."""
        self.playback_complete_event.clear()
        self.initial_buffer_fill()

        while not self.stop_event.is_set():
            try:
                if self.reset_event.is_set():
                    if not self.fade_out_event.is_set():
                        logger.debug("Reset event detected; initiating fade-out.")
                        self._initiate_fade_out()
                        self.reset_event.clear()
                    time.sleep(0.01)
                    continue

                try:
                    data = self.buffer.get(timeout=0.1)
                    if data is None:
                        break
                except queue.Empty:
                    logger.debug("Playback queue empty, waiting for data.")
                    time.sleep(0.1)
                    continue

                if self.fade_out_event.is_set() and self.total_fade_steps > 0:
                    audio_data = np.frombuffer(data, dtype=np.int16).astype(np.float32)
                    audio_data *= self.fade_volume
                    self.fade_volume -= self.fade_step
                    self.total_fade_steps -= 1
                    
                    if self.fade_volume < 0.0:
                        self.fade_volume = 0.0

                    data = audio_data.astype(np.int16).tobytes()
                    logger.debug(f"Applying fade-out: Remaining steps={self.total_fade_steps}, Current volume={self.fade_volume:.4f}")

                    if self.total_fade_steps <= 0:
                        logger.debug("Fade-out complete; clearing buffers.")
                        self.fade_out_event.clear()
                        self._clear_buffer()
                        self._reset_playback_state()

                self._write_data_to_stream(data)

                with self.buffer_lock:
                    self.buffers_played += 1
                logger.debug(f"Audio played. Buffers played count: {self.buffers_played}")

            except Exception as e:
                logger.error(f"Unexpected error in playback loop: {e}")

        logger.info("Playback thread terminated.")
        self.playback_complete_event.set()

    def _initiate_fade_out(self):
        """Initiates the fade-out process."""
        self.fade_out_event.set()
        fade_duration_sec = self.fade_out_duration / 1000.0
        self.total_fade_steps = int((fade_duration_sec * RATE) / FRAMES_PER_BUFFER)
        if self.total_fade_steps <= 0:
            self.total_fade_steps = 1
        self.fade_step = 1.0 / self.total_fade_steps
        self.fade_volume = 1.0
        logger.debug(f"Fade-out initiated: Duration={self.fade_out_duration}ms, Total steps={self.total_fade_steps}")

    def _reset_playback_state(self):
        """Resets the playback state after fade-out."""
        logger.debug("Resetting playback state.")
        with self.buffer_lock:
            self.buffers_played = 0
            self.min_buffer_fill = self.initial_min_buffer_fill
            self.reset_event.clear()
        logger.debug("Playback state has been reset.")

    def _write_data_to_stream(self, data: bytes):
        """Writes audio data to the PyAudio stream and handles wave file capture if enabled."""
        try:
            if self.enable_wave_capture and self.wave_file:
                self.wave_file.writeframes(data)
            self.stream.write(data)
        except IOError as e:
            logger.error(f"I/O error during stream write: {e}")
            try:
                self.stream.stop_stream()
                self.stream.start_stream()
                logger.info("PyAudio stream restarted after I/O error.")
            except Exception as restart_error:
                logger.error(f"Failed to restart PyAudio stream: {restart_error}")
        except Exception as e:
            logger.error(f"Unexpected error occurred while writing to stream: {e}")

    def initial_buffer_fill(self):
        """Fills the buffer initially to ensure smooth playback start."""
        logger.debug("Starting initial buffer fill.")
        while not self.stop_event.is_set():
            with self.buffer_lock:
                current_size = self.buffer.qsize()
            if current_size >= self.min_buffer_fill:
                break
            time.sleep(0.01)
        logger.debug("Initial buffer fill complete.")

    def enqueue_audio_data(self, audio_data: bytes):
        """Enqueues audio data into the playback buffer."""
        try:
            with self.buffer_lock:
                self.buffer.put(audio_data, timeout=1)
                logger.debug(f"Enqueued audio data. Queue size: {self.buffer.qsize()}")
        except queue.Full:
            logger.warning("Failed to enqueue audio data: Buffer full.")

    def _clear_buffer(self):
        """Clears all pending audio data from the buffer."""
        with self.buffer_lock:
            cleared_items = 0
            while not self.buffer.empty():
                try:
                    self.buffer.get_nowait()
                    cleared_items += 1
                except queue.Empty:
                    break
            logger.debug(f"Cleared {cleared_items} items from the buffer.")

    def drain_and_restart(self):
        """Configures the player to initiate a fade-out and reset playback."""
        with self.buffer_lock:
            logger.debug("Prepare for fade-out and reset.")
            self.fade_out_duration = 100
            self.reset_event.set()
            logger.info("Configured to reset with fade-out.")

    def close(self):
        """Closes the AudioPlayer, stopping playback and releasing resources."""
        logger.info("Closing AudioPlayer.")
        self.stop_event.set()
        self.buffer.put(None)
        self.playback_complete_event.wait(timeout=5)
        self.thread.join(timeout=5)
        if self.stream and self.stream.is_active():
            self.stream.stop_stream()
            logger.debug("PyAudio stream stopped.")
        if self.stream:
            self.stream.close()
            logger.debug("PyAudio stream closed.")
        self.pyaudio_instance.terminate()
        logger.debug("PyAudio terminated.")
        if self.enable_wave_capture and self.wave_file:
            try:
                self.wave_file.close()
                logger.info("Playback wave file saved successfully.")
            except Exception as e:
                logger.error(f"Error closing wave file for playback: {e}")
        logger.info("AudioPlayer stopped and resources released.")