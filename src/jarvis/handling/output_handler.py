from jarvis.config import BaseOutputHandler

import pyaudio
import asyncio

class MainOutputHandler(BaseOutputHandler):
    def __init__(self, ui):
        self.ui = ui

    def init_audio(self):
        self.audio = pyaudio.PyAudio()
        self.out_stream = self.audio.open(
            format=pyaudio.paInt16, 
            channels=1, 
            rate=24000, 
            output=True, 
            frames_per_buffer=512
        )
        self.audio_queue = asyncio.Queue()
        self._audio_running = True
        self.playback_task = asyncio.create_task(self._playback_loop())

    async def _playback_loop(self):
        loop = asyncio.get_running_loop()
        while self._audio_running:
            try:
                chunk = await self.audio_queue.get()
                await loop.run_in_executor(None, self.out_stream.write, chunk)
                self.audio_queue.task_done()
            except Exception:
                await asyncio.sleep(0.1)

    async def play_audio_chunk(self, audio_bytes: bytes):
        if hasattr(self, 'audio_queue'):
            await self.audio_queue.put(audio_bytes)

    def stop_audio(self):
        self._audio_running = False
        if hasattr(self, 'out_stream'):
            self.out_stream.stop_stream()
            self.out_stream.close()
            self.audio.terminate()

    async def broadcast(self, response_text: str) -> None:
        self.ui.print_message(response_text)