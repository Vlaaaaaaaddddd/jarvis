import os 
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage

from jarvis.config import BaseLLM, Gemini_model
from jarvis.utils.logger import get_logger

class Gemini(BaseLLM):
    def __init__(self):
        self.logger = get_logger("GeminiAPI")
        
        self.base_llm = ChatGoogleGenerativeAI(
            model=Gemini_model,
            temperature=0.4, 
            api_key=os.getenv("GEMINI_API_KEY")
        )

    async def generate_stateless(self, messages: list[BaseMessage], system_prompt: str = None, tools: list = None):
        try:
            clean_messages = []
            if system_prompt:
                clean_messages.append(SystemMessage(content=system_prompt))
                
            for m in messages:
                if isinstance(m, SystemMessage):
                    continue
                if isinstance(m, AIMessage) and not getattr(m, "tool_calls", None):
                    # Превращаем внутренние рассуждения агентов в "контекст" для следующего шага
                    clean_messages.append(HumanMessage(content=f"[Внутренний статус]: {m.content}"))
                else:
                    clean_messages.append(m)

            llm_with_tools = self.base_llm.bind_tools(tools) if tools else self.base_llm
            return await llm_with_tools.ainvoke(clean_messages)
            
        except Exception as e:
            import traceback
            self.logger.error(f"Gemini API Critical Error: {str(e)}\n{traceback.format_exc()}")
            raise