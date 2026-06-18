import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from starlette import status

from models import Users
from database import SessionLocal
from .auth import get_current_user
from tasks import write_audit_log

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/users",
    tags=["users"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[SessionLocal, Depends(get_db)]
user_dependency = Annotated[dict, Depends(get_current_user)]
bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class UserVerification(BaseModel):
    password: str
    new_password: str = Field(min_length=6)

@router.get("/", status_code=status.HTTP_200_OK)
async def get_user(user: user_dependency, db: db_dependency):
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return db.query(Users).filter(Users.id == user.get("id")).one_or_none()

@router.put("/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(user: user_dependency, db: db_dependency, user_verification: UserVerification, background_tasks: BackgroundTasks):
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    user_model = db.query(Users).filter(Users.id == user.get("id")).one_or_none()
    if not user_model:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not bcrypt_context.verify(user_verification.password, user_model.hashed_password):
        logger.warning("Password change failed for user %s — wrong current password", user.get('username'))
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Error on password change")

    user_model.hashed_password = bcrypt_context.hash(user_verification.new_password)
    db.add(user_model)
    db.commit()
    logger.info("Password changed for user %s", user.get('username'))
    background_tasks.add_task(write_audit_log, user.get('username'), "password_changed")

@router.put("/change_phone_number/{phone_number}", status_code=status.HTTP_204_NO_CONTENT)
async def change_phone_number(user: user_dependency, db: db_dependency, phone_number: str):
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    user_model = db.query(Users).filter(Users.id == user.get("id")).first()

    if not user_model:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user_model.phone_number = phone_number
    db.add(user_model)
    db.commit()
    logger.info("Phone number updated for user %s", user.get('username'))
