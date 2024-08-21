from typing import Annotated
from fastapi import FastAPI, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import schemes
from models import Base
from db import engine, get_db
from auth import get_db_user_with_email, register_user
from jwtUtils import create_access_token

Base.metadata.create_all(bind=engine)

app = FastAPI()


@app.post("/token")
async def login(
    form_Data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_db),
) -> schemes.Token:
    db_user = get_db_user_with_email(db, form_Data.username, form_Data.password)

    token = create_access_token(data={"sub": db_user.id, "email": db_user.email})

    return schemes.Token(
        access_token=token,
        token_type="bearer",
    )


@app.post("/signup")
def signup(
    user: schemes.UserCreate,
    db: Session = Depends(get_db),
) -> schemes.UserBase:
    new_user = register_user(db, user)

    return schemes.UserBase(
        id=new_user.id,
        name=new_user.name,
        email=new_user.email,
        role=new_user.role,
    )


@app.post("/product")
def create_product():
    return {"message": "Hello World"}
