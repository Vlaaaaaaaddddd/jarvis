from jarvis.services.gemini import Gemini
from jarvis.core.engine import JarvisEngine
from jarvis.front.render import JarvisUI
from jarvis.handling import MainInputHandler, MainOutputHandler

def create_app() -> JarvisEngine:
    """Фабричная функция сборки"""
    ui = JarvisUI()
    llm = Gemini()

    tts = None
    stt = None

    out_handler = MainOutputHandler(ui=ui, tts_service=tts)
    in_handler = MainInputHandler(ui=ui, stt_service=stt)
    
    # Собираем движок с внедренными зависимостями
    engine = JarvisEngine(ui=ui,
                          input_handler=in_handler, 
                          output_handler=out_handler, 
                          llm=llm)
    
    return engine