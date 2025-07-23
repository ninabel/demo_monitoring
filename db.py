# -*- coding: utf-8 -*-
"""
Author: Nina Belyavskaya
"""
from typing import Annotated
from fastapi import Depends
from sqlmodel import SQLModel, Session, create_engine

DATABASE_URL = "sqlite:///./test.db"  # or use ":memory:" for in-memory DB

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)

sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session

SessionDep = Annotated[Session, Depends(get_session)]