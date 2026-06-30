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