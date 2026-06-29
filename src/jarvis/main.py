import asyncio
from dotenv import load_dotenv
from jarvis.core import JarvisEngine
from jarvis.tools import TimeTool
from jarvis.services import Gemini

async def main():
    load_dotenv()
    print("Инициализация системы Джарвис...")

    ai_provider = Gemini()
    
    engine = JarvisEngine(llm=ai_provider)

    time_tool = TimeTool()
    engine.register_tool(time_tool)

    print("\nДжарвис готов к работе!")

    while True:
        user_input = input("\nВведите команду (или 'выход'): ")
        if user_input.strip().lower() in ['выход', 'exit', 'quit']:
            print("Завершение работы систем Джарвиса. До встречи!")
            break
        response = await engine.handle_command(user_input)
        print(response)

if __name__ == "__main__":
    asyncio.run(main())