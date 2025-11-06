from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from config import mysql_url, DB_ECHO

class Base(DeclarativeBase):
    pass

engine = create_engine(mysql_url(), echo=DB_ECHO, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)