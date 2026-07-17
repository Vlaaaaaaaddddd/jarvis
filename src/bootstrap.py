from jarvis.services import Gemini, GeminiLiveService, MemoryLLMService, EmbeddingService
from jarvis.core import JarvisEngine, TaskGraph, MemoryAgent
from jarvis.front.render import JarvisUI
from jarvis.handling import MainInputHandler, MainOutputHandler
from jarvis.tools.time_tool import time_tool
from jarvis.tools.calendar_tools import (
    calendar_add_event_tool, 
    calendar_add_task_tool, 
    calendar_get_schedule_tool
)
from jarvis.tools.approval_tool import request_user_approval_tool
from jarvis.tools.memory_tools import create_search_memory_tool
from jarvis.db.database import init_db
from jarvis.db.repository import PostgresRepository

import time

async def create_app() -> JarvisEngine:
    """Фабричная функция сборки"""
    current_session_id = str(int(time.time()))

    ui = JarvisUI()

    out_handler = MainOutputHandler(ui=ui)
    in_handler = MainInputHandler(ui=ui)
    
    # Память 
    await init_db()
    memory_repo = PostgresRepository()
    memory_llm_service = MemoryLLMService()
    embedding_service = EmbeddingService()

    memory_agent = MemoryAgent(
        repository=memory_repo, 
        llm_service=memory_llm_service,
        embedding_service=embedding_service)

    tools = [
        time_tool, 
        calendar_add_event_tool,
        calendar_add_task_tool,
        calendar_get_schedule_tool, 
        create_search_memory_tool(repository=memory_repo, embedding_service=embedding_service),
        request_user_approval_tool
    ]

    # Внутреннее ядро
    internal_llm = Gemini()
    task_graph = TaskGraph(llm=internal_llm, tools=tools)
    
    # Внешнее 
    live_service = GeminiLiveService()
    
    # Собираем движок с внедренными зависимостями
    engine = JarvisEngine(ui=ui,
                          input_handler=in_handler, 
                          output_handler=out_handler, 
                          task_graph=task_graph,
                          live_service=live_service,
                          memory_repo=memory_repo,
                          memory_agent=memory_agent,
                          session_id=current_session_id)
    
    return engine