import json

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import create_engine


sqlite_database = "sqlite+aiosqlite:///helper.db"
engine = create_engine(sqlite_database.replace("+aiosqlite", ""))
async_engine = create_async_engine(sqlite_database, future=True)
async_session = sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase): pass


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    fio = Column(String(256))
    group = Column(String(16))
    subdomain = Column(String(16))
    ssh_key = Column(Text)


class State(Base):
    __tablename__ = "states"
    id = Column(Integer, primary_key=True, index=True)
    vk_id = Column(String, unique=True)
    data = Column(Text)

    @hybrid_property
    def storage(self) -> dict:
        return json.loads(self.data)

    @storage.setter
    def set_data(self, value):
        self.data = json.dumps(value)

    def __str__(self):
        return f"User: {self.vk_id}; Data: {self.data}"


Base.metadata.create_all(bind=engine)
