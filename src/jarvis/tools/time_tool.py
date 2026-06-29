from jarvis.core import BaseTool
from jarvis.config import months, weekdays
from datetime import datetime


class TimeTool(BaseTool):    
    """Текущие дата и время"""
    @property
    def name(self): 
        return "TimeTool"
    
    async def execute(self):
        dt = datetime.now()
        month_ru = months[dt.month]
        weekday_ru = weekdays[dt.weekday()]
        time_str = dt.strftime("%H:%M:%S")
        return f"{dt.day} {month_ru}, {weekday_ru}, {time_str}"
