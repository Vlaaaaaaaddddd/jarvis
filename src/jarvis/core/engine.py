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
        self._is_running = True

        self._audio_task = asyncio.create_task(self._audio_player_loop())

        if hasattr(self.input_handler, 'start_microphone'):
            self.input_handler.start_microphone()

        if hasattr(self.output_handler, 'init_audio'):
            self.output_handler.init_audio()

        live_task = asyncio.create_task(
            self.live_service.start(
                on_delegate=self._handle_delegation,
                on_memorize=self._handle_memorizing,
                on_text_received=self._handle_live_text,
                on_audio_received=self._handle_live_audio
            )
        )

        if hasattr(self.input_handler, 'microphone_loop'):
            self._tasks.append(asyncio.create_task(
                self.input_handler.microphone_loop(self.live_service.send_audio)
            ))
        
        if hasattr(self.input_handler, 'keyboard_loop'):
            self._tasks.append(asyncio.create_task(
                self.input_handler.keyboard_loop(self.live_service.send_text)
            ))

        # Держим движок активным, пока работает флаг
        while self._is_running:
            await asyncio.sleep(0.1)

    async def _audio_player_loop(self):
        """Асинхронный воркер, который непрерывно читает очередь и воспроизводит звук"""
        while self._is_running:
            try:
                audio_bytes = await self._audio_queue.get()
                if hasattr(self.output_handler, 'play_audio_chunk'):
                    await self.output_handler.play_audio_chunk(audio_bytes)
                self._audio_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                pass

    async def _handle_delegation(self, query: str) -> str:
        """Коллбек: Внешний интерфейс просит внутренний выполнить тяжелую задачу"""
        if hasattr(self.ui, 'terminal_ui'):
            self.ui.terminal_ui.status = "ДЖАРВИС ДУМАЕТ..."
        
        if self.memory_repo:
            try:
                await self.memory_repo.append_session_log(
                    session_id=self.session_id, 
                    role="user", 
                    content=query)
            except Exception as e:
                with open("debug_memory.log", "a", encoding="utf-8") as f:
                    f.write(f"[Memory Error] Не удалось записать запрос: {e}\n")

        response = await self.agent.run(query)

        if self.memory_repo:
            try:
                await self.memory_repo.append_session_log(
                    session_id=self.session_id, 
                    role="assistant", 
                    content=response)
            except Exception:
                pass
        
        if hasattr(self.ui, 'terminal_ui'):
            self.ui.terminal_ui.status = "СИСТЕМА АКТИВНА"
            
        return response
    
    async def _handle_memorizing(self, fact: str):
        """Обработка запоминания факта в памяти"""
        if hasattr(self.ui, 'terminal_ui'):
            self.ui.terminal_ui.status = "Сохранил в память"
        if self.memory_repo:
            try:
                await self.memory_repo.append_session_log(
                    session_id=self.session_id, 
                    role="fact", 
                    content=fact
                )
                if hasattr(self.ui, 'terminal_ui'):
                    self.ui.terminal_ui.status = "СИСТЕМА АКТИВНА"
                return f"Успешно зафиксировано в памяти сессии факт: '{fact}'"
            except Exception as e:
                if hasattr(self.ui, 'terminal_ui'):
                    self.ui.terminal_ui.status = "СИСТЕМА АКТИВНА"
                return f"Ошибка при записи факта в репозиторий: {str(e)}"
        
        
        
        return "Репозиторий памяти не инициализирован в движке."

    async def _handle_live_text(self, text: str) -> None:
        """Коллбек: Внешняя модель сгенерировала текстовый транскрипт ответа"""
        await self.output_handler.broadcast(text)


    async def _handle_live_audio(self, audio_bytes: bytes) -> None:
        """Коллбек: Внешняя модель сгенерировала аудио-чанк"""
        await self._audio_queue.put(audio_bytes)

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