from typing import Union
from pydantic import BaseModel, EmailStr, SecretStr


class Token(BaseModel):
    access_token: str
    token_type: str


class UserCredentials(BaseModel):
    email: EmailStr
    password: SecretStr


class UserBase(BaseModel):
    id: int
    name: str
    role: str
    email: EmailStr


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    plain_password: SecretStr


class UserInDB(UserBase):
    hashed_password: SecretStr
