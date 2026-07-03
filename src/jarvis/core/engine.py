import asyncio
import time
import jarvis.config.ui_config as cfg
from jarvis.config import BaseUI, BaseInputHandler, BaseOutputHandler, BaseLiveService

class JarvisEngine:
    def __init__(self, 
                 ui: BaseUI,
                 input_handler: BaseInputHandler, 
                 output_handler: BaseOutputHandler, 
                 agent, 
                 live_service: BaseLiveService
                 ):
        self.ui = ui
        self.input_handler = input_handler
        self.output_handler = output_handler
        self.agent = agent
        self.live_service = live_service

        self._is_running = False
        self._tasks = []

    async def start(self):
        """Запуск основного цикла приложения"""
        await self.ui.start()
        self._is_running = True

        if hasattr(self.input_handler, 'start_microphone'):
            self.input_handler.start_microphone()

        if hasattr(self.output_handler, 'init_audio'):
            self.output_handler.init_audio()

        live_task = asyncio.create_task(
            self.live_service.start(
                on_delegate=self._handle_delegation,
                on_text_received=self._handle_live_text,
                on_audio_received=self._handle_live_audio
            )
        )

        mic_task = asyncio.create_task(
            self.input_handler.microphone_loop(on_audio_callback=self.live_service.send_audio)
        )
        kbd_task = asyncio.create_task(
            self.input_handler.keyboard_loop(on_text_callback=self.live_service.send_text)
        )

        self._tasks = [live_task, mic_task, kbd_task]

        try:
            await asyncio.gather(*self._tasks)
        except asyncio.CancelledError:
            pass
        finally:
            self.stop()

    async def _handle_delegation(self, query: str) -> str:
        """Коллбек: Внешний интерфейс просит внутренний выполнить тяжелую задачу"""
        if hasattr(self.ui, 'terminal_ui'):
            self.ui.terminal_ui.status = "ДЖАРВИС ДУМАЕТ..."

        response = await self.agent.run(query)
        
        if hasattr(self.ui, 'terminal_ui'):
            self.ui.terminal_ui.status = "СИСТЕМА АКТИВНА"
            
        return response

    async def _handle_live_text(self, text: str) -> None:
        """Коллбек: Внешняя модель сгенерировала текстовый транскрипт ответа"""
        await self.output_handler.broadcast(text)


    async def _handle_live_audio(self, audio_bytes: bytes) -> None:
        """Коллбек: Внешняя модель сгенерировала аудио-чанк"""
        if hasattr(self.output_handler, 'play_audio_chunk'):
            await self.output_handler.play_audio_chunk(audio_bytes)

    def stop(self):
        if self._is_running:
            self._is_running = False
            if self.ui:
                self.ui.stop()
            if hasattr(self.input_handler, 'stop'):
                self.input_handler.stop()
            if hasattr(self.output_handler, 'stop_audio'):
                self.output_handler.stop_audio()
            # Отменяем фоновые таски
            for task in self._tasks:
                if not task.done():
                    task.cancel()