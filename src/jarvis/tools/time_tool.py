from datetime import datetime
from langchain_core.tools import tool
from jarvis.config import months, weekdays

@tool("TimeTool")
def time_tool() -> str:
    """Возвращает текущую дату, день недели и точное время. Не требует параметров.
    ВАЖНО: Вызывай этот инструмент перед добавлением или просмотром событий в календаре!
    """
    dt = datetime.now()
    month_ru = months[dt.month]
    weekday_ru = weekdays[dt.weekday()]
    time_str = dt.strftime("%H:%M:%S")
    
    # Добавляем строгий ISO-формат в начале для парсинга моделью
    return (
        f"[ТЕКУЩАЯ ДАТА ДЛЯ СИС-ВЫЧИСЛЕНИЙ]: {dt.strftime('%Y-%m-%d')}\n"
        f"Человеческий формат: {dt.year} год, {dt.day} {month_ru}, {weekday_ru}, {time_str}"
    )