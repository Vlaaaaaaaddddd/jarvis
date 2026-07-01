from jarvis.front.ui import TerminalUI 
from jarvis.services.gemini import Gemini
from jarvis.core.engine import JarvisEngine

def create_app() -> JarvisEngine:
    """Фабричная функция сборки"""
    ui = TerminalUI()
    llm = Gemini()
    
    # Собираем движок с внедренными зависимостями
    engine = JarvisEngine(ui=ui, llm=llm)
    
    return engine