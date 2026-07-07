from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from jarvis.db.database import Base

class UserProfile(Base):
    """Горячая память"""
    __tablename__ = 'user_profile'
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, nullable=False, index=True)
    value = Column(Text, nullable=False)

class VectorMemory(Base):
    """Теплая память"""
    __tablename__ = 'vector_memory'
    
    id = Column(Integer, primary_key=True, index=True)
    text = Column(Text, nullable=False)
    # Размерность 768 
    embedding = Column(Vector(768)) 
    meta_data = Column(JSON, nullable=True) # Здесь можно хранить теги или даты

class SessionLog(Base):
    """Холодная память"""
    __tablename__ = 'session_log'
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True, nullable=False)
    role = Column(String, nullable=False) # user, assistant или system
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())