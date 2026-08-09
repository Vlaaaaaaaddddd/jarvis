import asyncio
import pyaudio
from jarvis.config import BaseInputHandler
from jarvis.utils.logger import get_logger

logger = get_logger("input")

class MainInputHandler(BaseInputHandler):
    def __init__(self, ui):
        self.ui = ui
        self._running = False
        
        # Настройки микрофона под Live API
        self.audio = pyaudio.PyAudio()
        self.in_stream = None

        self._input_buffer = ""

    def start(self) -> None:
        self._running = True
        try:
            self.in_stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000, # 16kHz для Gemini Live
                input=True,
                frames_per_buffer=1024
            )
        except Exception as e:
            logger.error("Не удалось инициализировать микрофон: %s", e)
    async def microphone_loop(self, on_audio_callback):
        """Непрерывное чтение аудио и отправка через коллбек"""
        loop = asyncio.get_running_loop()
        while self._running:
            if self.in_stream and self.in_stream.is_active():
                try:
                    data = await loop.run_in_executor(None, self.in_stream.read, 1024, False)
                    await on_audio_callback(data)
                except Exception:
                    await asyncio.sleep(0.1)
            else:
                await asyncio.sleep(0.1)

    async def keyboard_loop(self, on_text_callback):
        """Обработка ввода с клавиатуры"""
        while self._running:
            term = self.ui.terminal_ui.term
            key = await asyncio.to_thread(term.inkey, timeout=None)

            if key.code == term.KEY_ENTER:
                user_command = self.ui.terminal_ui.input_buffer.strip()
                self._input_buffer = ""
                self.ui.update_input_buffer(self._input_buffer)

                if user_command:
                    self.ui.print_user_message(user_command)
                    await on_text_callback(user_command)

            elif key.code in (term.KEY_BACKSPACE, term.KEY_DELETE):
                self._input_buffer = self._input_buffer[:-1]
                self.ui.update_input_buffer(self._input_buffer)
            elif not key.is_sequence:
                self._input_buffer += key
                self.ui.update_input_buffer(self._input_buffer)

    def stop(self) -> None:
        self._running = False
        if self.in_stream:
            self.in_stream.stop_stream()
            self.in_stream.close()
            self.in_stream = None
            
        if self.audio:
            self.audio.terminate()