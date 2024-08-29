from fastapi import HTTPException
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from models import User
from schemes import UserBase, UserCreate

password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password, hashed_password):
    return password_context.verify(plain_password, hashed_password)


def hash_password(password: str):
    return password_context.hash(password)


def get_db_user_by_email(db: Session, email: str):
    db_user = db.query(User).filter(User.email == email).first()

    if not db_user:
        raise HTTPException(status_code=401, detail="Incorrect email.")

    return UserBase(
        id=db_user.id, name=db_user.name, role=db_user.role, email=db_user.email
    )


def authenticate_user(db: Session, email: str, plain_password: str):
    db_user = db.query(User).filter(User.email == email).first()

    if not db_user or not verify_password(plain_password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    return UserBase(
        id=db_user.id, name=db_user.name, role=db_user.role, email=db_user.email
    )


def register_user(db: Session, user: UserCreate):
    hashed_password = hash_password(user.plain_password.get_secret_value())

    new_user = User(
        name=user.name,
        email=user.email,
        hashed_password=hashed_password,
        role="admin",
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return UserBase(
        id=new_user.id, name=new_user.name, role=new_user.role, email=new_user.email
    )
