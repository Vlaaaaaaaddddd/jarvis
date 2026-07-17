import json
from langchain_core.tools import StructuredTool
from jarvis.services.embeddings import EmbeddingService
from jarvis.db.repository import PostgresRepository

def create_search_memory_tool(repository: PostgresRepository, embedding_service: EmbeddingService, llm_service) -> StructuredTool:
    """Фабрика для продвинутого инструмента RAG-поиска с декомпозицией запросов"""
    
    async def search_user_memory(query: str) -> str:
        """
        Используй этот инструмент для глубокого поиска по долговременной памяти, 
        предпочтениям, планам и неформальным контекстам пользователя.
        Инструмент автоматически разбивает сложные многосоставные запросы на атомарные темы.
        """
        try:
            if not query or not query.strip():
                return "Поисковый запрос пуст"

            # Быстрая декомпозиция сложного запроса силами LLM
            decomposition_prompt = (
                "Ты — поисковый оптимизатор базы знаний. Разбей сложный запрос пользователя на "
                "отдельные, короткие, независимые ключевые слова или сущности для точечного векторного поиска. "
                "Игнорируй союзы и глаголы. Выдели только чистые объекты.\n"
                f"Запрос для анализа: '{query}'\n"
                "Верни ответ СТРОГО в формате JSON: [\"сущность1\", \"сущность2\"] без markdown и рассуждений."
            )
            
            try:
                raw_keywords = await llm_service.analyze_facts(
                    facts_payload=decomposition_prompt, 
                    system_instruction="Ты возвращаешь только чистый JSON массив строк."
                )
                keywords = json.loads(raw_keywords)
            except Exception:
                keywords = [query]

            # Изолированный поиск по каждому ключевому слову
            all_memories = []
            seen_texts = set()

            for kw in keywords:
                query_vector = await embedding_service.get_embedding(kw)
                if not query_vector:
                    continue
                
                # Используем наш репозиторий с отсечением мусора
                memories = await repository.search_vector_memory(query_vector, limit=2, threshold=0.55)
                
                for mem in memories:
                    text = mem.get('text', '')
                    if text and text not in seen_texts:
                        seen_texts.add(text)
                        all_memories.append(mem)

            if not all_memories:
                return f"В долговременной памяти не найдено релевантных записей по ключам: {keywords}"

            # Форматируем результат для Агента-Исследователя
            formatted_results = [f"=== РЕЗУЛЬТАТЫ УМНОГО ПОИСКА ПО ПАМЯТИ (Ключи: {keywords}) ==="]
            for idx, mem in enumerate(all_memories, 1):
                text = mem.get('text', '')
                meta = mem.get('metadata') or {}
                date_str = meta.get('created_at', 'Дата не указана')
                formatted_results.append(f"{idx}. [{date_str}] {text}")
                
            return "\n".join(formatted_results)

        except Exception as e:
            return f"Ошибка при выполнении умного RAG-поиска: {str(e)}"

    return StructuredTool.from_function(
        coroutine=search_user_memory,
        name="search_user_memory",
        description="Поиск по долговременной семантической памяти пользователя (автоматически дробит сложные запросы)."
    )