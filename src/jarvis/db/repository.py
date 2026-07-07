from sqlalchemy import select
from jarvis.config import BaseMemoryRepository
from jarvis.db.database import async_session_maker
from jarvis.db.models import UserProfile, VectorMemory, SessionLog

class PostgresRepository(BaseMemoryRepository):
    # ХОЛОДНАЯ ПАМЯТЬ: Буфер сообщений, который будет анализировать агент памяти
    async def append_session_log(self, session_id: str, role: str, content: str) -> None:
        """Сохраняет реплику диалога в сырые логи базы данных"""
        async with async_session_maker() as session:
            async with session.begin():
                log = SessionLog(session_id=session_id, role=role, content=content)
                session.add(log)

    async def get_session_logs(self, session_id: str, limit: int = 100) -> list:
        """Возвращает историю текущей сессии для контекста"""
        async with async_session_maker() as session:
            stmt = (
                select(SessionLog)
                .where(SessionLog.session_id == session_id)
                .order_by(SessionLog.timestamp.asc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            logs = result.scalars().all()
            return [
                {"role": log.role, "content": log.content, "timestamp": log.timestamp} 
                for log in logs
            ]

    # ГОРЯЧАЯ ПАМЯТЬ: Самые важные данные, которые нужно помнить постоянно
    async def update_user_profile(self, key: str, value: str) -> None:
        """Обновляет или добавляет фиксированный факт о пользователе"""
        async with async_session_maker() as session:
            async with session.begin():
                stmt = select(UserProfile).where(UserProfile.key == key)
                result = await session.execute(stmt)
                profile = result.scalar_one_or_none()
                
                if profile:
                    profile.value = value
                else:
                    session.add(UserProfile(key=key, value=value))

    async def get_user_profile(self) -> dict:
        """Возвращает все известные жесткие факты о пользователе"""
        async with async_session_maker() as session:
            stmt = select(UserProfile)
            result = await session.execute(stmt)
            profiles = result.scalars().all()
            return {p.key: p.value for p in profiles}

    # ТЕПЛАЯ ПАМЯТЬ: Семантический RAG 
    async def add_vector_memory(self, text: str, embedding: list, metadata: dict = None) -> None:
        """Сохраняет факт и его эмбеддинг в pgvector"""
        async with async_session_maker() as session:
            async with session.begin():
                memory_entry = VectorMemory(text=text, embedding=embedding, meta_data=metadata)
                session.add(memory_entry)

    async def search_vector_memory(self, query_embedding: list, limit: int = 5) -> list:
        """Делает косинусное расстояние (или L2) по векторам и возвращает похожие факты"""
        async with async_session_maker() as session:
            stmt = (
                select(VectorMemory)
                .order_by(VectorMemory.embedding.cosine_distance(query_embedding))
                .limit(limit)
            )
            result = await session.execute(stmt)
            memories = result.scalars().all()
            return [{"text": m.text, "metadata": m.meta_data} for m in memories]