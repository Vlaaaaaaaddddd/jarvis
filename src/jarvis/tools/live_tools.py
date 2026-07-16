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
                    description=(
                        "Делегировать сложную системную задачу (работа с календарем, расписанием, памятью) внутреннему агенту. "
                        "ВАЖНО: Если внутренний агент возвращает сообщение с текстом '[СИСТЕМНЫЙ СТАТУС]: Требуется подтверждение', "
                        "ты ОБЯЗАН озвучить предложенный им черновик пользователю голосом, спросить его подтверждение или правки, "
                        "и получив ответ от пользователя, СНОВА вызвать этот инструмент (delegate_heavy_task), "
                        "передав ответ пользователя в параметр query для завершения планирования. Не принимай решения за пользователя самостоятельно."
                    ),
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "query": types.Schema(
                                type="STRING", 
                                description="Оригинальный текстовый запрос пользователя ИЛИ его вербальный ответ/правки к черновику плана."
                            )
                        },
                        required=["query"]
                    )
                )
            ]
        )

    async def execute(self, query: str) -> str:
        return await self._callback(query)
    

class MemorizeFactTool:
    def __init__(self, on_memorize_callback):
        self.on_memorize = on_memorize_callback

    @property
    def name(self) -> str:
        return "memorize_important_fact"
    
    def get_schema(self) -> types.Tool:
        return types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name=self.name,
                    description="Вызывай, когда пользователь сообщает (или возвращает внутренний агент) важные факты о себе, своих планах, коде, проектах или настройках, которые нужно железно запомнить на будущее.",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "fact": types.Schema(
                                type="STRING", 
                                description="Четко сформулированный атомарный факт на русском языке в утвердительной форме. Пример: 'Пользователь разрабатывает бренд ESTO на Python' или 'У пользователя день рождения 2 мая'."
                            )
                        },
                        required=["fact"]
                    )
                )
            ]
        )

    async def execute(self, fact: str) -> str:
        return await self.on_memorize(fact)
    
class ForceConsolidationTool(BaseTool):
    def __init__(self, on_force_callback):
        self.on_force = on_force_callback
    @property
    def name(self) -> str:
        return "force_memory_consolidation"
    
    def get_schema(self) -> types.Tool:
        return types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name=self.name,
                    description="Используй этот инструмент ТОЛЬКО, если пользователь говорит, что отходит на какое-тоо время, или прямо просит запустить анализ, очистку или структурирование памяти, когда можно запустить внутреннего Агента Памяти",
                )
            ]
        )
    
    async def execute(self, **kwargs):
        return await self.on_force()