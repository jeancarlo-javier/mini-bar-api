from pydantic import BaseModel, EmailStr, SecretStr
from typing import Literal


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
    password: SecretStr


class UserInDB(UserBase):
    hashed_password: SecretStr


class ProductCreate(BaseModel):
    name: str
    description: str
    price: float
    production_cost: float


class ProductPublic(BaseModel):
    id: int
    name: str
    description: str
    price: float
    archived: bool


class OrderBase(BaseModel):
    id: int
    order_time: str
    last_order_time: str
    status: str
    note: str
    user: UserBase
    table_number: int
    total: float


class OrderCreate(BaseModel):
    table_number: int


class OrderItemBase(BaseModel):
    id: int
    product_id: int
    quantity: int
    status: str
    paid: bool
    order_id: int


class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int


class OrderItemPublic(BaseModel):
    id: int
    product: ProductPublic
    order_time: str
    quantity: int
    amount: float
    status: str
    paid: bool
    order_id: int


class OrderItemToggleStatus(BaseModel):
    status: Literal["item_status", "item_payment_status"]
