import os
import asyncio
import pyaudio
from jarvis.config import BaseInputHandler

class MainInputHandler(BaseInputHandler):
    def __init__(self, ui):
        self.ui = ui
        self._running = False
        
        # Настройки микрофона под Live API
        self.audio = pyaudio.PyAudio()
        self.in_stream = None

    def start_microphone(self):
        self._running = True
        self.in_stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000, # 16kHz для Gemini Live
            input=True,
            frames_per_buffer=1024
        )

    async def microphone_loop(self, on_audio_callback):
        """Непрерывное чтение аудио и отправка через коллбек"""
        loop = asyncio.get_running_loop()
        while self._running:
            if self.in_stream and self.in_stream.is_active():
                try:
                    data = await loop.run_in_executor(None, self.in_stream.read, 1024, False)
                    await on_audio_callback(data)
                except Exception as e:
                    # Ловим падения PyAudio или коллбека
                    with open("debug_live.log", "a", encoding="utf-8") as f:
                        f.write(f"[MIC LOOP ERROR]: {repr(e)}\n")
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
                self.ui.terminal_ui.input_buffer = "" 
                if user_command:
                    self.ui.print_user_message(user_command)
                    await on_text_callback(user_command)
            elif key.code in (term.KEY_BACKSPACE, term.KEY_DELETE) or key == '\x7f':
                self.ui.terminal_ui.input_buffer = self.ui.terminal_ui.input_buffer[:-1]
            elif not key.is_sequence:
                self.ui.terminal_ui.input_buffer += key

    def stop(self):
        self._running = False
        if self.in_stream:
            self.in_stream.stop_stream()
            self.in_stream.close()
        self.audio.terminate()