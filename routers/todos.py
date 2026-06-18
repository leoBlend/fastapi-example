import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path
from pydantic import BaseModel, Field
from starlette import status

from models import Todos
from database import SessionLocal
from .auth import get_current_user
from tasks import write_audit_log

logger = logging.getLogger(__name__)

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[SessionLocal, Depends(get_db)]
user_dependency = Annotated[dict, Depends(get_current_user)]

class TodoRequest(BaseModel):
    title: str = Field(min_length=3)
    description: str = Field(min_length=3, max_length=100)
    priority: int = Field(gt=0, lt=6)
    complete: bool = Field(default=False)

@router.get("/", status_code=status.HTTP_200_OK)
async def read_all(user: user_dependency, db: db_dependency):
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Auth failed.')
    return db.query(Todos).filter(Todos.owner_id == user.get('id')).all()

@router.get("/todos/{todo_id}", status_code=status.HTTP_200_OK)
async def read_todo(user: user_dependency, db: db_dependency, todo_id: int = Path(gt=0)):
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Auth failed.')

    todo_model = db.query(Todos).filter(Todos.id == todo_id, Todos.owner_id == user.get('id')).first()

    if not todo_model:
        logger.warning("Todo %d not found for user %s", todo_id, user.get('username'))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Todo not found.')
    return todo_model

@router.post("/todo", status_code=status.HTTP_201_CREATED)
async def create_todo(user: user_dependency, db: db_dependency, todo_request: TodoRequest, background_tasks: BackgroundTasks):
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Auth failed.')

    todo_model = Todos(**todo_request.model_dump(), owner_id=user.get('id'))

    db.add(todo_model)
    db.commit()
    logger.info("Todo created by user %s: '%s'", user.get('username'), todo_request.title)
    background_tasks.add_task(write_audit_log, user.get('username'), "todo_created",
                              f"title={todo_request.title}, priority={todo_request.priority}")

@router.put("/todos/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_todo(user: user_dependency, db: db_dependency, todo_request: TodoRequest, todo_id: int = Path(gt=0)):
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Auth failed.')

    todo_model = db.query(Todos).filter(Todos.id == todo_id, Todos.owner_id == user.get('id')).first()

    if not todo_model:
        logger.warning("Update failed — todo %d not found for user %s", todo_id, user.get('username'))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Todo not found.')

    todo_model.title = todo_request.title
    todo_model.description = todo_request.description
    todo_model.priority = todo_request.priority
    todo_model.complete = todo_request.complete

    db.add(todo_model)
    db.commit()
    logger.info("Todo %d updated by user %s", todo_id, user.get('username'))

@router.delete("/todos/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_todo(user: user_dependency, db: db_dependency, background_tasks: BackgroundTasks, todo_id: int = Path(gt=0)):
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Auth failed.')

    todo_model = db.query(Todos).filter(Todos.id == todo_id, Todos.owner_id == user.get('id')).first()

    if not todo_model:
        logger.warning("Delete failed — todo %d not found for user %s", todo_id, user.get('username'))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Todo not found.')

    db.query(Todos).filter(Todos.id == todo_id).delete()
    db.commit()
    logger.info("Todo %d deleted by user %s", todo_id, user.get('username'))
    background_tasks.add_task(write_audit_log, user.get('username'), "todo_deleted",
                              f"todo_id={todo_id}")
