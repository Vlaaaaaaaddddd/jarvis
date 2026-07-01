from abc import ABC, abstractmethod

class BaseTool(ABC): 

    @property
    @abstractmethod
    def name(self) -> str: 
        pass

    @abstractmethod
    async def execute(self): 
        pass

class BaseLLM(ABC): 
    @abstractmethod
    async def generate_response(self, prompt: str) -> str:
        """Принимает текст от пользователя, возвращает ответ от LLM"""
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
    async def listen(self) -> str:
        pass

class BaseOutputHandler(ABC):
    @abstractmethod
    async def broadcast(self, response_text: str) -> None:
        pass