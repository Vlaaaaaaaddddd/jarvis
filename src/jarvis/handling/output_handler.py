import pyaudio
import asyncio
from jarvis.config import BaseOutputHandler

class MainOutputHandler(BaseOutputHandler):
    def __init__(self, ui):
        self.ui = ui
        self.audio = None
        self.out_stream = None
        self.audio_queue = None
        self.playback_task = None
        self._audio_running = False

    def start(self) -> None:
        self.audio = pyaudio.PyAudio()
        try:
            self.out_stream = self.audio.open(
                format=pyaudio.paInt16, 
                channels=1, 
                rate=24000,
                output=True, 
                frames_per_buffer=512
            )
        except Exception:
            pass

        self.audio_queue = asyncio.Queue()
        self._audio_running = True
        self.playback_task = asyncio.create_task(self._playback_loop())

    async def _playback_loop(self):
        loop = asyncio.get_running_loop()
        while self._audio_running:
            try:
                chunk = await self.audio_queue.get()
                if self.out_stream and self._audio_running:
                    await loop.run_in_executor(None, self.out_stream.write, chunk)
                self.audio_queue.task_done()
            except Exception:
                await asyncio.sleep(0.1)

    async def play_audio_chunk(self, audio_bytes: bytes):
        if self._audio_running and self.audio_queue:
            await self.audio_queue.put(audio_bytes)

    async def broadcast(self, text: str) -> None:
        self.ui.print_message(text)

    def stop(self) -> None:
        self._audio_running = False
        
        if self.playback_task:
            self.playback_task.cancel()
            self.playback_task = None

        if self.out_stream:
            self.out_stream.stop_stream()
            self.out_stream.close()
            self.out_stream = None

        if self.audio:
            self.audio.terminate()
            self.audio = None
