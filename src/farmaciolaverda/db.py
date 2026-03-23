from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase
from .config import DB_URL

engine = create_engine(DB_URL)

print("DB_URL:", DB_URL)

class Base(DeclarativeBase):
    pass