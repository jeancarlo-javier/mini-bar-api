from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from models import Base, Product, Order, OrderItem
from db import engine, get_db
from auth import authenticate_user, register_user, get_db_user_by_email
from jwtUtils import create_access_token, decode_token
from typing import Annotated
import schemes
from security import oauth2_scheme

Base.metadata.create_all(bind=engine)

app = FastAPI()


@app.post("/token", response_model=schemes.Token, tags=["auth"])
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_db),
):
    db_user = authenticate_user(db, form_data.username, form_data.password)

    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    token = create_access_token(data={"sub": db_user.id, "email": db_user.email})

    return schemes.Token(access_token=token, token_type="bearer")


@app.post("/signup", response_model=schemes.UserBase, tags=["auth"])
def signup(
    user: schemes.UserCreate,
    db: Session = Depends(get_db),
):
    new_user = register_user(db, user)

    return schemes.UserBase(
        id=new_user.id,
        name=new_user.name,
        email=new_user.email,
        role=new_user.role,
    )


# Products
@app.get(
    "/products/{product_id}", response_model=schemes.ProductCreate, tags=["products"]
)
def read_product(
    product_id: int,
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db),
):
    decoded = decode_token(token)
    user = get_db_user_by_email(db, decoded["email"])
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
        )

    product = db.query(Product).filter(Product.id == product_id).first()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found."
        )

    return product


@app.post("/products", response_model=schemes.ProductCreate, tags=["products"])
def create_product(
    form_data: schemes.ProductCreate,
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db),
):
    decoded = decode_token(token)
    user = get_db_user_by_email(db, decoded["email"])

    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
        )

    new_product = Product(
        name=form_data.name, description=form_data.description, price=form_data.price
    )
    db.add(new_product)
    db.commit()
    db.refresh(new_product)

    return new_product


@app.get("/products", response_model=list[schemes.ProductCreate], tags=["products"])
def read_products(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db),
):
    decoded = decode_token(token)

    products = db.query(Product).all()

    return products


@app.put(
    "/products/{product_id}", response_model=schemes.ProductCreate, tags=["products"]
)
def update_product(
    product_id: int,
    form_data: schemes.ProductCreate,
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db),
):
    decoded = decode_token(token)
    user = get_db_user_by_email(db, decoded["email"])

    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
        )

    product = db.query(Product).filter(Product.id == product_id).first()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found."
        )

    product.name = form_data.name
    product.description = form_data.description
    product.price = form_data.price

    db.commit()

    return product


@app.delete("/products/{product_id}", tags=["products"])
def delete_product(
    product_id: int,
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db),
):
    decoded = decode_token(token)
    user = get_db_user_by_email(db, decoded["email"])

    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
        )

    product = db.query(Product).filter(Product.id == product_id).first()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found."
        )

    db.delete(product)
    db.commit()

    return {"message": "Product was deleted successfully"}


# Orders
@app.post("/orders", response_model=schemes.OrderCreate, tags=["orders"])
def create_order(
    form_data: schemes.OrderCreate,
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db),
):
    decoded = decode_token(token)
    user = get_db_user_by_email(db, decoded["email"])

    if user.role != "staff" and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
        )

    new_order = Order(
        user_id=decoded["sub"],
        status="pending",
        table_number=form_data.table_number,
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)

    return new_order


@app.get("/orders/{order_id}", response_model=schemes.OrderCreate, tags=["orders"])
def read_order(
    order_id: int,
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db),
):
    decoded = decode_token(token)
    user = get_db_user_by_email(db, decoded["email"])

    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
        )

    order = db.query(Order).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Order not found."
        )

    return order


@app.get("/orders", response_model=list[schemes.OrderCreate], tags=["orders"])
def read_orders(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db),
):
    decoded = decode_token(token)
    user = get_db_user_by_email(db, decoded["email"])

    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
        )

    orders = db.query(Order).all()

    return orders


@app.post(
    "/orders/{order_id}/items", response_model=schemes.OrderItemCreate, tags=["orders"]
)
def create_order_item(
    order_id: int,
    form_data: schemes.OrderItemCreate,
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db),
):
    decoded = decode_token(token)
    user = get_db_user_by_email(db, decoded["email"])

    if user.role != "staff" and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
        )

    # Check if the order exists
    order = db.query(Order).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Order not found."
        )

    new_order_item = OrderItem(
        order_id=order_id,
        product_id=form_data.product_id,
        quantity=form_data.quantity,
    )

    db.add(new_order_item)
    db.commit()
    db.refresh(new_order_item)

    return new_order_item
