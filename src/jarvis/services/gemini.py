import os 
from google import genai

from jarvis.config import BaseLLM

class Gemini(BaseLLM):
    def __init__(self):
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model_name = "gemini-2.5-flash"
    
    async def generate_response(self, prompt: str) -> str:
        response = await self.client.aio.models.generate_content(
            model=self.model_name,
            contents=prompt,
        )
        return response.text