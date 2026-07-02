import asyncio
from google.genai import types

from jarvis.config import BaseLLM, BaseTool

class AgentOrchestrator:
    def __init__(self, llm: BaseLLM, tools: list[BaseTool]):
        self.llm = llm
        self.tools_map = {tool.name: tool for tool in tools}

    async def run(self, user_prompt: str) -> str:
        """
        В будущем этот метод будет заменен на вызов графа: await app.ainvoke(...)
        """
        response = await self.llm.generate_response(user_prompt)
        
        while response.function_calls:
            tool_responses = []
            tasks = []
            call_infos = []
            
            # Собираем все функции, которые модель хочет выполнить параллельно
            for function_call in response.function_calls:
                func_name = function_call.name
                func_args = function_call.args 
                
                if func_name in self.tools_map:
                    tasks.append(self.tools_map[func_name].execute(**func_args))
                    call_infos.append(function_call)
                else:
                    # Защита: если модель придумала несуществующий инструмент
                    return f"Модель запросила неизвестный инструмент {func_name}"
            
            # Асинхронно выполняем все инструменты
            results = await asyncio.gather(*tasks)

            for function_call, result in zip(call_infos, results):
                tool_responses.append(
                    types.Part.from_function_response(
                        name=function_call.name,
                        response={"result": result} 
                    )
                )
            
            response = await self.llm.generate_response(tool_responses)

        return response.text