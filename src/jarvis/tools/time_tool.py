from jarvis.config import months, weekdays, BaseTool
from datetime import datetime
from google.genai import types


class TimeTool(BaseTool):    
    """Текущие дата и время"""
    @property
    def name(self): 
        return "TimeTool"
    
    def get_schema(self) -> dict:
        return types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name=self.name,
                    description="Возвращает текущую дату, день недели и точное время. Не требует параметров."
                    # Аргументы добавляются так (на будущее)
                    # parameters=types.Schema(
                    #     type=types.Type.OBJECT,
                    #     properties={
                    #         "location": types.Schema(type=types.Type.STRING, description="Город")
                    #     },
                    #     required=["location"]
                    # )
                )
            ]
        )
    
    async def execute(self, **kwargs):
        dt = datetime.now()
        month_ru = months[dt.month]
        weekday_ru = weekdays[dt.weekday()]
        time_str = dt.strftime("%H:%M:%S")
        return f"{dt.day} {month_ru}, {weekday_ru}, {time_str}"
