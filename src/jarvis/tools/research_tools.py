from langchain_core.tools import tool
from jarvis.services.tavily import TavilySearchService

# Инициализируем инфраструктуру на уровне модуля, как и календарь
search_infra = TavilySearchService()

@tool
async def internet_search_tool(query: str) -> str:
    """Выполняет поиск в интернете
    Незаменим для получения актуальных данных, новостей и аналитических справок и прочего
    
    Args:
        query: Четко сформулированный поисковый запрос на естественном языке
    """
    try:
        raw_response = await search_infra.execute_search(query=query, search_depth="advanced", max_results=3)
        
        answer = raw_response.get("answer", "")
        results = raw_response.get("results", [])
        
        if not results and not answer:
            return f"Поиск по запросу '{query}' не принес результатов."

        # Форматируем структурированный отчёт для контекста LLM
        report = f"=== РЕЗУЛЬТАТЫ ПОИСКА В ИНТЕРНЕТЕ ===\n"
        report += f"Запрос: {query}\n\n"
        
        if answer:
            report += f"[СИНТЕЗИРОВАННЫЙ ОТВЕТ]:\n{answer}\n\n"
            
        report += "[РАСШИРЕННЫЕ ИСТОЧНИКИ]:\n"
        for idx, res in enumerate(results, 1):
            title = res.get('title', 'Без названия')
            url = res.get('url', 'URL отсутствует')
            content = res.get('content', '')[:250]
            report += f"{idx}. {title}\n   Ссылка: {url}\n   Выжимка: {content}...\n"
            
        return report

    except ValueError as ve:
        # Перехватываем проблему отсутствия ключа
        return f"Ошибка конфигурации: {str(ve)}"
    except Exception as e:
        # Все остальные сетевые или API ошибки
        return f"Ошибка при выполнении веб-поиска: {str(e)}"