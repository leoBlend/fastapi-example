import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# Load DATABASE_URL (and friends) from the .env file at the project root.
load_dotenv()

# Postgres connection string, e.g.
#   postgresql+psycopg2://postgres:postgres@localhost:5432/todoapp
# Comes from .env so the app, Alembic, and tests share one source of truth.
SQL_ALCHEMY_DATABASE_URL = os.environ["DATABASE_URL"]

# Note: no more `check_same_thread` — that was a SQLite-only quirk. Postgres is a
# real client/server database with proper connection pooling.
engine = create_engine(SQL_ALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
