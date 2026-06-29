from jarvis.core import BaseTool, BaseLLM

class JarvisEngine:
    def __init__(self, llm: BaseLLM = None):
        self._tools = {}
        self._llm = llm
    def register_tool(self, tool: BaseTool):
        command_name = tool.name.lower()
        self._tools[command_name] = tool
        print(f"[Engine] Инструмент успешно подключен: {tool.name}")

    async def handle_command(self, user_input: str) -> str:
        """Получаем команду от пользователя и ищет подходящий инструмент"""
        command = user_input.strip().lower()

        if not command:
            return "Команда пустая"
        
        if command in self._tools:
            tool = self._tools[command]
            return await tool.execute()
        if self._llm:
            print('\nДжарвис: ')
            return await self._llm.generate_response(user_input)
        
        return f"Команды '{user_input}' нет, и ИИ-ассистент не подключен."