import os 
from google import genai
from google.genai import types

from jarvis.config import BaseLLM, Gemini_model, systm_prompt, live_model_system_prompt

class Gemini(BaseLLM):
    def __init__(self, tools: list = None):

        self.config = types.GenerateContentConfig(
            system_instruction=systm_prompt,
            tools=tools or [],
            temperature=0.4, 
        )

        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model_name = Gemini_model
        self.chat = self.client.aio.chats.create(
            model=self.model_name,
            config=self.config)
    
    async def generate_response(self, prompt: str) -> str:

        response = await self.chat.send_message(prompt)
        
        return response