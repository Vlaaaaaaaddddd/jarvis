import asyncio
from jarvis.config import BaseUI, BaseInputHandler, BaseOutputHandler, BaseLiveService

class JarvisEngine:
    def __init__(self, 
                 ui: BaseUI,
                 input_handler: BaseInputHandler, 
                 output_handler: BaseOutputHandler, 
                 agent, 
                 live_service: BaseLiveService, 
                 memory_repo = None, 
                 session_id = None
                 ):
        self.ui = ui
        self.input_handler = input_handler
        self.output_handler = output_handler
        self.agent = agent
        self.live_service = live_service
        self.memory_repo = memory_repo
        self.session_id = session_id

        self._is_running = False
        self._tasks = []

        self._audio_queue = asyncio.Queue()
        self._audio_task = None

    async def start(self):
        """Запуск основного цикла приложения"""
        await self.ui.start()

        self.input_handler.start()
        self.output_handler.start()

        self._is_running = True

        live_task = asyncio.create_task(
            self.live_service.start(
                on_delegate=self._handle_delegation,
                on_memorize=self._handle_memorizing,
                on_text_received=self._handle_live_text,
                on_audio_received=self._handle_live_audio
            )
        )
        self._tasks.append(live_task)

        self._tasks.extend([
            asyncio.create_task(self.input_handler.microphone_loop(self.live_service.send_audio)),
            asyncio.create_task(self.input_handler.keyboard_loop(self.live_service.send_text))
        ])

        while self._is_running:
            await asyncio.sleep(0.1)

    async def _handle_delegation(self, query: str) -> str:
        """Коллбек: Внешний интерфейс просит внутренний выполнить тяжелую задачу"""
        self.ui.set_status("ДЖАРВИС ДУМАЕТ...")
        try:
            response = await self.agent.run(query)
            return response
        except Exception as e:
            return f"Внутренняя ошибка агента при обработке: {str(e)}"
        finally:
            self.ui.set_status("СИСТЕМА АКТИВНА")
    
    async def _handle_memorizing(self, fact: str) -> str:
        """Коллбек: Запрос на сохранение важного факта в базу данных сессии"""
        self.ui.set_status("ФИКСАЦИЯ ПАМЯТИ...")
        
        if not self.memory_repo or not self.session_id:
            self.ui.set_status("СИСТЕМА АКТИВНА")
            return "Репозиторий памяти не инициализирован"

        try:
            await self.memory_repo.append_session_log(
                session_id=self.session_id,
                role="fact", 
                content=fact
            )
            return f"Успешно зафиксировано в памяти сессии факт: '{fact}'"
        except Exception as e:
            return f"Ошибка при записи факта в репозиторий: {str(e)}"
        finally:
            self.ui.set_status("СИСТЕМА АКТИВНА")

    async def _handle_live_text(self, text: str) -> None:
        await self.output_handler.broadcast(text)

    async def _handle_live_audio(self, audio_bytes: bytes) -> None:
        await self.output_handler.play_audio_chunk(audio_bytes)

    def stop(self):
        if self._is_running:
            self._is_running = False

            self.ui.stop()
            self.input_handler.stop()
            self.output_handler.stop()

            for task in self._tasks:
                if not task.done():
                    task.cancel()
            self._tasks.clear()