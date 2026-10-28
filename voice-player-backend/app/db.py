from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


class Database:
    def __init__(self, url: str):
        kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
        self.engine = create_engine(url, **kwargs)
        self._factory = sessionmaker(self.engine, expire_on_commit=False)

    def create_all(self) -> None:
        from . import models  # noqa: F401  注册表
        Base.metadata.create_all(self.engine)

    def session(self) -> Session:
        return self._factory()
