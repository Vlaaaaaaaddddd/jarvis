from google.genai import types
from jarvis.config import BaseTool
from jarvis.services.embeddings import EmbeddingService
from jarvis.db.repository import PostgresRepository

class SearchMemoryTool(BaseTool):
    """
    Инструмент RAG для Бэк-офиса Джарвиса
    """
    def __init__(self, repository: PostgresRepository, embedding_service: EmbeddingService):
        self.repo = repository
        self.embedding_service = embedding_service

    @property
    def name(self) -> str:
        return "search_user_memory"

    def get_schema(self) -> types.Tool:
        return types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name=self.name,
                    # Прописываем жесткую инструкцию для исключения конфликта инструментов
                    description=(
                        "Используй этот инструмент для поиска по долговременной памяти, воспоминаниям, "
                        "заметкам, предпочтениям, а также МЯГКИМ или НЕФОРМАЛЬНЫМ ПЛАНАМ, намерениям и задачам пользователя, "
                        "которые он упоминал в прошлых разговорах"
                        "ВАЖНО: Если пользователь спрашивает про свои планы, расписание или дела на день, ты "
                        "ОБЯЗАН вызвать этот инструмент СОВМЕСТНО с инструментом Календаря (get_calendar_events), "
                        "чтобы объединить жесткий график из календаря и неформальные контексты из памяти"
                    ),
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "query": types.Schema(
                                type="STRING",
                                description="Поисковый запрос на естественном языке, сформулированный для поиска по памяти (например: 'планы на пятницу', 'наработки по Docker', 'цели бренда ESTO')."
                            )
                        },
                        required=["query"]
                    )
                )
            ]
        )

    async def execute(self, query: str) -> str:
        """
        Векторизуем текстовый запрос 
        Делаем SELECT по косинусному расстоянию
        Форматируем результаты в читаемый текст
        """
        try:
            if not query or not query.strip():
                return "Поисковый запрос пуст"

            query_vector = await self.embedding_service.get_embedding(query)
            if not query_vector:
                return "Системная ошибка: Не удалось сгенерировать вектор для поиска."

            # Передаем вектор. Ограничиваем выдачу топ-5 релевантных фактов
            memories = await self.repo.search_vector_memory(query_vector, limit=5)
            
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