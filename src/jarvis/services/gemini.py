import os 
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import BaseMessage, SystemMessage

from jarvis.config import BaseLLM, Gemini_model, systm_prompt
from jarvis.utils.logger import get_logger

class Gemini(BaseLLM):
    def __init__(self, tools: list = None):
        self.logger = get_logger("GeminiAPI")
        
        # Элегантная инициализация модели
        self.llm = ChatGoogleGenerativeAI(
            model=Gemini_model,
            temperature=0.4, 
            api_key=os.getenv("GEMINI_API_KEY")
        )
        
        # Привязываем инструменты напрямую, LangChain сам соберет JSON-схемы
        if tools:
            self.llm = self.llm.bind_tools(tools)

    async def generate_stateless(self, messages: list[BaseMessage]):
        try:
            if not any(isinstance(m, SystemMessage) for m in messages):
                messages = [SystemMessage(content=systm_prompt)] + messages

            # ainvoke сам конвертирует BaseMessage в формат Google и обратно
            response = await self.llm.ainvoke(messages)
            return response
        except Exception as e:
            import traceback
            self.logger.error(f"Gemini API Critical Error: {str(e)}\n{traceback.format_exc()}")
            raise