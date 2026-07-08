import os
from google import genai
from google.genai import types
from jarvis.config import BaseMemoryManager, Gemini_model 

class MemoryLLMService(BaseMemoryManager):
    """Изолированный сервис генерации для Агента Памяти (Stateless, JSON-only)"""
    def __init__(self):
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model_name = Gemini_model
        
    async def analyze_facts(self, facts_payload: str, system_instruction: str) -> str:
        """Отправляет факты на анализ и гарантированно возвращает JSON-строку"""
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json", 
            temperature=0.1
        )
        
        response = await self.client.aio.models.generate_content(
            model=self.model_name,
            contents=facts_payload,
            config=config
        )
        return response.text