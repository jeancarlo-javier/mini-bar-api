from fastapi import FastAPI, Depends
from models import Base
from db import engine, get_db
from sqlalchemy.orm import Session

Base.metadata.create_all(bind=engine)

app = FastAPI()


@app.get("/")
def read_root():
    return {"message": "Hello World"}
