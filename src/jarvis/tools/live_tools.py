from google.genai import types
from jarvis.config import BaseTool 

class DelegateHeavyTaskTool(BaseTool):
    def __init__(self, on_delegate_callback):
        self._callback = on_delegate_callback

    @property
    def name(self) -> str:
        return "delegate_heavy_task"

    def get_schema(self) -> types.Tool:
        return types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name=self.name,
                    description="Делегировать сложную системную задачу или задачу требующую точных данных, знаний времени, локации, работу с календарем или БД внутреннему агенту.",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "query": types.Schema(
                                type="STRING", 
                                description="Оригинальный текстовый запрос пользователя для обработки бэк-офисом."
                            )
                        },
                        required=["query"]
                    )
                )
            ]
        )

    async def execute(self, query: str) -> str:
        return await self._callback(query)