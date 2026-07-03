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
    def start(self) -> None:
        pass

    @abstractmethod
    def render_frame(self, current_time: float) -> None:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass

class BaseInputHandler(ABC):
    @abstractmethod
    async def microphone_loop(self, on_audio_callback):
        pass

    @abstractmethod
    async def keyboard_loop(self, on_text_callback):
        pass

class BaseOutputHandler(ABC):
    @abstractmethod
    async def broadcast(self, response_text: str) -> None:
        pass