from langchain_core.tools import StructuredTool
from jarvis.services.embeddings import EmbeddingService
from jarvis.db.repository import PostgresRepository

def create_search_memory_tool(repository: PostgresRepository, embedding_service: EmbeddingService) -> StructuredTool:
    """Фабрика для инструмента RAG-поиска по Бэк-офису"""
    
    async def search_user_memory(query: str) -> str:
        """
        Используй этот инструмент для поиска по долговременной памяти, воспоминаниям, 
        заметкам, предпочтениям, а также МЯГКИМ или НЕФОРМАЛЬНЫМ ПЛАНАМ, намерениям и задачам пользователя, 
        которые он упоминал в прошлых разговорах.
        
        ВАЖНО: Если пользователь спрашивает про свои планы, расписание или дела на день, ты 
        ОБЯЗАН вызвать этот инструмент СОВМЕСТНО с инструментом Календаря, 
        чтобы объединить жесткий график из календаря и неформальные контексты из памяти.

        Args:
            query: Поисковый запрос на естественном языке, сформулированный для поиска по памяти (например: 'планы на пятницу', 'наработки по Docker').
        """
        try:
            if not query or not query.strip():
                return "Поисковый запрос пуст"

            query_vector = await embedding_service.get_embedding(query)
            if not query_vector:
                return "Системная ошибка: Не удалось сгенерировать вектор для поиска."

            memories = await repository.search_vector_memory(query_vector, limit=5)
            
            if not memories:
                return "В долговременной семантической памяти не найдено релевантных записей"

            formatted_results = ["=== РЕЗУЛЬТАТЫ ПОИСКА ИЗ ДОЛГОВРЕМЕННОЙ ПАМЯТИ ==="]
            for idx, mem in enumerate(memories, 1):
                text = mem.text if hasattr(mem, 'text') else mem.get('text', '')
                meta = mem.meta_data if hasattr(mem, 'meta_data') else mem.get('meta_data', {})
                date_str = meta.get('created_at', 'Дата не указана') if meta else 'Дата не указана'
                
                formatted_results.append(f"{idx}. [{date_str}] {text}")
                
            return "\n".join(formatted_results)

        except Exception as e:
            return f"Ошибка при выполнении RAG-поиска по памяти: {str(e)}"

    return StructuredTool.from_function(
        coroutine=search_user_memory,
        name="search_user_memory",
        description="Поиск по долговременной семантической памяти пользователя (предпочтения, планы, факты)."
    )