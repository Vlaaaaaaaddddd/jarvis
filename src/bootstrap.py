from jarvis.services import Gemini, GeminiLiveService, MemoryLLMService, EmbeddingService
from jarvis.core import JarvisEngine, AgentOrchestrator, MemoryAgent
from jarvis.front.render import JarvisUI
from jarvis.handling import MainInputHandler, MainOutputHandler
from jarvis.tools import (
    TimeTool, 
    CalendarAddEventTool, CalendarAddTaskTool, CalendarGetScheduleTool,
    SearchMemoryTool)
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
        TimeTool(), 
        CalendarAddEventTool(),
        CalendarAddTaskTool(),
        CalendarGetScheduleTool(), 
        SearchMemoryTool(repository=memory_repo, embedding_service=embedding_service)
    ]
    tools_schemas = [tool.get_schema() for tool in tools]

    # Внутреннее ядро
    internal_llm = Gemini(tools=tools_schemas)
    agent = AgentOrchestrator(llm=internal_llm, tools=tools)
    
    # Внешнее 
    live_service = GeminiLiveService()
    
    # Собираем движок с внедренными зависимостями
    engine = JarvisEngine(ui=ui,
                          input_handler=in_handler, 
                          output_handler=out_handler, 
                          agent=agent, 
                          live_service=live_service,
                          memory_repo=memory_repo,
                          memory_agent=memory_agent,
                          session_id=current_session_id)
    
    return engine