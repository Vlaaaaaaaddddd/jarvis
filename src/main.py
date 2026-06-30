import asyncio
import sys
from dotenv import load_dotenv
from jarvis.core.engine import JarvisEngine

async def main():
    load_dotenv()

    engine = JarvisEngine()
    
    try:
        await engine.start()
    except KeyboardInterrupt:
        engine.stop()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(main())