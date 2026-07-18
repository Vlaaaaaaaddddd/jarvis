import os
from tavily import AsyncTavilyClient

class TavilySearchService:
    """Инфраструктурный сервис для взаимодействия с поисковой системой Tavily API"""
    
    def __init__(self):
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            raise ValueError("Tavily API ключ не настроен или отсутствует в .env")
        
        self.client = AsyncTavilyClient(api_key=api_key)

    async def execute_search(self, query: str, search_depth: str = "advanced", max_results: int = 3):
        return await self.client.search(
            query=query,
            search_depth=search_depth,
            include_answer=True,
            max_results=max_results
        )