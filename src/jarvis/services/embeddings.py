import os
from google import genai
from google.genai import types

class EmbeddingService:
    """Сервис для работы с эмбеддингами"""
    def __init__(self):
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model_name = "gemini-embedding-2"

    async def get_embedding(self, text: str) -> list:
        """
        Генерация эмбеддинга для одной строки текста
        """
        if not text or not text.strip():
            return []

        response = await self.client.aio.models.embed_content(
            model=self.model_name,
            contents=text.strip(),
            config=types.EmbedContentConfig(output_dimensionality=768)
        )
        if response.embeddings and len(response.embeddings) > 0:
            return response.embeddings[0].values
        return []

    async def get_embeddings_batch(self, texts: list[str]) -> list[list]:
        """
        Пакетная генерация эмбеддингов
        """
        if not texts:
            return []

        cleaned_texts = [t.strip() for t in texts if t and t.strip()]
        if not cleaned_texts:
            return []

        # Обертка в типы SDK для обхода бага слияния списков строк
        contents = [
            types.Content(parts=[types.Part.from_text(text=t)])
            for t in cleaned_texts
        ]

        # Бьем на куски, если накопилось много текстов
        all_embeddings = []
        chunk_size = 100
        
        for i in range(0, len(contents), chunk_size):
            chunk = contents[i:i + chunk_size]
            response = await self.client.aio.models.embed_content(
                model=self.model_name,
                contents=chunk,
                config=types.EmbedContentConfig(output_dimensionality=768)
            )
            if response.embeddings:
                all_embeddings.extend([emb.values for emb in response.embeddings])
                
        return all_embeddings