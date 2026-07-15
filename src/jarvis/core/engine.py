import asyncio
import time
from jarvis.config import BaseUI, BaseInputHandler, BaseOutputHandler, BaseLiveService, live_model_system_prompt
from jarvis.core.graph import TaskGraph

class JarvisEngine:
    def __init__(self, 
                 ui: BaseUI,
                 input_handler: BaseInputHandler, 
                 output_handler: BaseOutputHandler, 
                 task_graph: TaskGraph,
                 live_service: BaseLiveService, 
                 memory_repo = None, 
                 memory_agent = None,
                 session_id = None
                 ):
        self.ui = ui
        self.input_handler = input_handler
        self.output_handler = output_handler
        self.task_graph = task_graph
        self.live_service = live_service
        self.memory_repo = memory_repo
        self.memory_agent = memory_agent
        self.session_id = session_id

        self._is_running = False
        self._tasks = []

        self._audio_queue = asyncio.Queue()
        self._audio_task = None

        self.last_activity_time = time.time()
        self.idle_timeout = 120  # 2 минуты тишины
        self.is_consolidating = False
        self.consolidation_task = None

    async def _compile_system_prompt(self) -> str:
        base_prompt = live_model_system_prompt
        
        if not self.memory_repo:
            return base_prompt

        try:
            # Тянем горячие факты
            profile_data = await self.memory_repo.get_user_profile()
            if not profile_data:
                return base_prompt

            # Красиво форматируем их в список для модели
            facts_lines = [f"- {key}: {value}" for key, value in profile_data.items()]
            facts_block = "\n".join(facts_lines)

            # Собираем финальный пирог
            dynamic_prompt = (
                f"{base_prompt}\n\n"
                f"=== АКТУАЛЬНЫЙ КОНТЕКСТ ПОЛЬЗОВАТЕЛЯ (ГОРЯЧАЯ ПАМЯТЬ) ===\n"
                f"Ты обязан учитывать эти проверенные факты о пользователе в текущей сессии:\n"
                f"{facts_block}\n"
                f"======================================================="
            )
            return dynamic_prompt

        except Exception as e:
            self.ui.print_message(f"[System] Ошибка сборки динамического промпта: {e}")
            return base_prompt

    async def start(self):
        """Запуск основного цикла приложения"""
        await self.ui.start()

        self.input_handler.start()
        self.output_handler.start()

        self._is_running = True

        dynamic_prompt = await self._compile_system_prompt()

        live_task = asyncio.create_task(
            self.live_service.start(
                on_delegate=self._handle_delegation,
                on_memorize=self._handle_memorizing,
                on_force_consolidation=self._handle_force_consolidation,
                on_audio_received=self._handle_live_audio,
                system_prompt=dynamic_prompt
            )
        )
        self._tasks.append(live_task)

        self._tasks.extend([
            asyncio.create_task(self.input_handler.microphone_loop(self.live_service.send_audio)),
            asyncio.create_task(self.input_handler.keyboard_loop(self.live_service.send_text))
        ])

        while self._is_running:
            await asyncio.sleep(0.1)
            if self.memory_agent and not self.is_consolidating:
                if (time.time() - self.last_activity_time) > self.idle_timeout:
                    self.is_consolidating = True
                    self.consolidation_task = asyncio.create_task(self._run_consolidation())

    async def _handle_delegation(self, query: str) -> str:
        """Коллбек: Внешний интерфейс просит внутренний выполнить тяжелую задачу"""
        self.ui.set_status("ДЖАРВИС ДУМАЕТ...")
        self._wake_up()
        try:
            response = await self.task_graph.run(query)
            return response
        except Exception as e:
            return f"Внутренняя ошибка агента при обработке: {str(e)}"
        finally:
            self.ui.set_status("СИСТЕМА АКТИВНА")
    
    async def _handle_memorizing(self, fact: str) -> str:
        """Коллбек: Запрос на сохранение важного факта в базу данных сессии"""
        self.ui.set_temporary_status("ФИКСАЦИЯ ПАМЯТИ...", duration=3.0)
        self._wake_up()
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

    async def _handle_live_audio(self, audio_bytes: bytes) -> None:
        self._wake_up(from_user=False)
        await self.output_handler.play_audio_chunk(audio_bytes)

    async def _handle_force_consolidation(self) -> str:
        """Коллбек: Принудительный запуск консолидации по просьбе пользователя"""
        if self.is_consolidating:
            return "Агент памяти уже работает."
        
        self.is_consolidating = True
        self.consolidation_task = asyncio.create_task(self._run_consolidation())
        return "Анализ памяти запущен. Перехожу в спящий режим."

    async def _run_consolidation(self):
        """Фоновый запуск Агента Памяти"""
        try:
            self.ui.set_status("РАБОТАЕТ АГЕНТ ПАМЯТИ")
            await self.memory_agent.consolidate()
        except Exception as e:
            self.ui.print_message(f"[System] Ошибка памяти: {e}")
        finally:
            self.last_activity_time = time.time()
            self.is_consolidating = False
            self.ui.set_status("СИСТЕМА АКТИВНА")

    def _wake_up(self, from_user: bool = True):
        """Сброс таймера и прерывание сна/консолидации при любой активности"""
        self.last_activity_time = time.time()
        
        if from_user and self.is_consolidating and self.consolidation_task:
            # Если агент памяти работает — жестоко убиваем его задачу
            self.consolidation_task.cancel()
            self.is_consolidating = False
            self.consolidation_task = None
            self.ui.set_status("СИСТЕМА АКТИВНА")

    

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