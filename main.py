import models
from fastapi import FastAPI
from starlette import status
from database import engine
from routers import auth, todos, admin, users

app = FastAPI()

models.Base.metadata.create_all(bind=engine)
app.include_router(auth.router)
app.include_router(todos.router)
app.include_router(admin.router)
app.include_router(users.router)


@app.get("/healthy", status_code=status.HTTP_200_OK)
def health_check():
    return {"status": "Healthy"}
