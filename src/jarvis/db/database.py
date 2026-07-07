from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
from jarvis.config import DATABASE_URL

# Создаем асинхронный движок
engine = create_async_engine(DATABASE_URL, echo=False)

# Фабрика подключений 
async_session_maker = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# Базовый класс для всех моделей
Base = declarative_base()

async def init_db():
    """Создает расширение pgvector и все таблицы, если их нет"""
    async with engine.begin() as conn:
        # активируем векторное расширение
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        # Создаем таблицы по моделям
        await conn.run_sync(Base.metadata.create_all)