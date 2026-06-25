from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from pgvector.sqlalchemy import Vector

from database import Base

# Dimension of the all-MiniLM-L6-v2 embedding model (see embeddings.py).
EMBEDDING_DIM = 384

class Users(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True)
    email = Column(String, unique=True)
    first_name = Column(String)
    last_name = Column(String)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    role = Column(String)
    phone_number = Column(String)

class Todos(Base):
    __tablename__ = 'todos'

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    description = Column(String)
    priority = Column(Integer)
    complete = Column(Boolean, default=False)
    owner_id = Column(Integer, ForeignKey('users.id'))
    # The semantic embedding of this todo's title+description. Nullable so a todo
    # can exist before its vector is computed (and for backfilling old rows).
    embedding = Column(Vector(EMBEDDING_DIM), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id        = Column(Integer, primary_key=True, index=True)
    username  = Column(String)
    action    = Column(String)
    detail    = Column(String, default="")
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
