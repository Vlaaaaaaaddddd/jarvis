from abc import ABC, abstractmethod

class BaseLLM(ABC): 
    @abstractmethod
    async def generate_response(self, prompt: str) -> str:
        """Принимает текст от пользователя, возвращает ответ от LLM"""
        pass

class BaseLiveService(ABC):
    @abstractmethod
    async def start(self, on_delegate, on_text_received, on_audio_received) -> None:
        """
        Запускает сессию Live API 
        on_delegate: коллбек для передачи тяжелых задач внутреннему агенту
        on_text_received: коллбек для передачи текстового транскрипта в UI
        on_audio_received: коллбек для передачи аудио-чанков в обработчик вывода
        """
        pass

    @abstractmethod
    async def send_text(self, text: str) -> None:
        """Отправляет текстовую команду от пользователя напрямую в активную Live-сессию"""
        pass

    @abstractmethod
    async def send_audio(self, pcm_data: bytes) -> None:
        """Отправляет аудио-данные в активную Live-сессию"""
        pass

    @abstractmethod
    async def stop(self) -> None:
        pass

class BaseMemoryManager(ABC):
    @abstractmethod
    async def analyze_facts(self, facts_payload: str, system_instruction: str) -> str:
        """Отправляет факты на анализ и гарантированно возвращает JSON-строку"""
        pass

class BaseTool(ABC): 
    @property
    @abstractmethod
    def name(self) -> str: 
        pass

    @abstractmethod
    def get_schema(self) -> dict:
        """Возвращает JSON-схему инструмента для LLM"""
        pass

    @abstractmethod
    async def execute(self): 
        pass


class BaseUI(ABC):
    @abstractmethod
    async def start(self) -> None:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass

    @abstractmethod
    def set_status(self, status: str) -> None:
        pass

    @abstractmethod
    def print_message(self, text: str) -> None:
        pass

    @abstractmethod
    def print_user_message(self, text: str) -> None:
        pass

    @abstractmethod
    def update_input_buffer(self, text: str) -> None:
        pass

class BaseInputHandler(ABC):
    @abstractmethod
    def start(self) -> None:
        pass

    @abstractmethod
    async def microphone_loop(self, on_audio_callback):
        pass

    @abstractmethod
    async def keyboard_loop(self, on_text_callback):
        pass

    @abstractmethod 
    def stop(self) -> None:
        pass

class BaseOutputHandler(ABC):
    @abstractmethod
    def start(self) -> None:
        pass

    @abstractmethod
    async def broadcast(self, response_text: str) -> None:
        pass

    @abstractmethod
    async def play_audio_chunk(self, audio_bytes: bytes) -> None:
        pass

    @abstractmethod 
    def stop(self) -> None:
        pass

class BaseMemoryRepository(ABC):
    # ХОЛОДНАЯ ПАМЯТЬ: Буфер сообщений, который будет анализировать агент памяти
    @abstractmethod
    async def append_session_log(self, session_id: str, role: str, content: str) -> None:
        """Сохраняет реплику диалога в сырые логи базы данных"""
        pass

    @abstractmethod
    async def get_session_logs(self, session_id: str, limit: int = 100) -> list:
        """Возвращает историю текущей сессии для контекста"""
        pass

    # ГОРЯЧАЯ ПАМЯТЬ: Самые важные данные, которые нужно помнить постоянно
    @abstractmethod
    async def update_user_profile(self, key: str, value: str) -> None:
        """Обновляет или добавляет фиксированный факт о пользователе"""
        pass

    @abstractmethod
    async def get_user_profile(self) -> dict:
        """Возвращает все известные жесткие факты о пользователе"""
        pass

    # ТЕПЛАЯ ПАМЯТЬ: Семантический RAG 
    async def add_vector_memory(self, text: str, embedding: list, metadata: dict = None) -> None:
        """Сохраняет факт и его эмбеддинг в pgvector"""
        pass

    @abstractmethod
    async def search_vector_memory(self, query_embedding: list, limit: int = 5) -> list:
        """Делает косинусное расстояние (или L2) по векторам и возвращает похожие факты"""
        pass

    # МЕТОДЫ АГЕНТА ПАМЯТИ 
    @abstractmethod
    async def get_unprocessed_facts(self) -> list:
        """
        Выбирает из session_log все важные необработанные факты
        """
        pass

    @abstractmethod
    async def mark_facts_as_processed(self, log_ids: list) -> None:
        """
        Помечает пачку записей как обработанные
        """
        pass

    @abstractmethod
    async def delete_user_profile_key(self, key: str) -> None:
        """
        Удаляет ключ из горячей памяти
        Нужно, если Агент поймет, что какой-то факт о пользователе стал неактуален
        """
        pass