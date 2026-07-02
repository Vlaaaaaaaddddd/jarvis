from jarvis.services.gemini import Gemini
from jarvis.core import JarvisEngine, AgentOrchestrator
from jarvis.front.render import JarvisUI
from jarvis.handling import MainInputHandler, MainOutputHandler
from jarvis.tools import TimeTool

def create_app() -> JarvisEngine:
    """Фабричная функция сборки"""
    ui = JarvisUI()

    tools = [
        TimeTool()
    ]
    tools_schemas = [tool.get_schema() for tool in tools]

    llm = Gemini(tools=tools_schemas)

    agent = AgentOrchestrator(llm=llm, tools=tools)

    tts = None
    stt = None


    out_handler = MainOutputHandler(ui=ui, tts_service=tts)
    in_handler = MainInputHandler(ui=ui, stt_service=stt)
    
    # Собираем движок с внедренными зависимостями
    engine = JarvisEngine(ui=ui,
                          input_handler=in_handler, 
                          output_handler=out_handler, 
                          agent=agent)
    
    return engine