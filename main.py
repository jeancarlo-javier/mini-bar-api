from typing import Union
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from models import Base, Product, Order, OrderItem
from db import engine, get_db
from auth import authenticate_user, register_user, get_db_user_by_email
from jwtUtils import create_access_token, decode_token
from typing import Annotated
import schemes
from datetime import datetime
from security import oauth2_scheme
from sqlalchemy import DateTime

Base.metadata.create_all(bind=engine)

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Helper function to check if the user has the required role
def verify_role(required_role: str, token: str, db: Session) -> None:
    decoded = decode_token(token)
    user = get_db_user_by_email(db, decoded["email"])
    if user.role != required_role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
        )


# Helper function to convert datetime to string
def format_datetime(dt_obj: Union[DateTime, datetime]) -> str:
    if isinstance(dt_obj, datetime):
        return dt_obj.strftime("%Y-%m-%d %H:%M:%S")
    raise TypeError("Unsupported type for datetime formatting")


@app.post("/login", response_model=schemes.Token, tags=["auth"])
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
    verify_role("admin", token, db)
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
    verify_role("admin", token, db)

    new_product = Product(**form_data.model_dump())
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    return new_product


@app.get("/products", response_model=list[schemes.ProductPublic], tags=["products"])
def read_products(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db),
):
    products = db.query(Product).all()

    return [
        schemes.ProductPublic(
            id=product.id,
            name=product.name,
            description=product.description,
            price=product.price,
        )
        for product in products
    ]


@app.put(
    "/products/{product_id}", response_model=schemes.ProductCreate, tags=["products"]
)
def update_product(
    product_id: int,
    form_data: schemes.ProductCreate,
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db),
):
    verify_role("admin", token, db)

    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found."
        )

    for key, value in form_data.model_dump().items():
        setattr(product, key, value)

    db.commit()
    return product


@app.delete("/products/{product_id}", tags=["products"])
def delete_product(
    product_id: int,
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db),
):
    verify_role("admin", token, db)

    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found."
        )

    db.delete(product)
    db.commit()
    return {"message": "Product was deleted successfully"}


# Orders
@app.post("/orders", response_model=schemes.OrderBase, tags=["orders"])
def create_order(
    form_data: schemes.OrderCreate,
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db),
):
    # verify_role("staff", token, db)

    new_order = Order(
        user_id=decode_token(token)["sub"],
        status="pending",
        table_number=form_data.table_number,
    )
    db.add(new_order)
    db.commit()

    new_order.set_local_order_time(region="America/Lima")
    db.commit()

    db.refresh(new_order)

    return schemes.OrderBase(
        id=new_order.id,
        order_time=format_datetime(new_order.order_time),
        status=new_order.status,
        user_id=new_order.user_id,
        table_number=new_order.table_number,
    )


@app.get("/orders/{order_id}", response_model=schemes.OrderBase, tags=["orders"])
def read_order(
    order_id: int,
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db),
):
    verify_role("admin", token, db)

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Order not found."
        )
    return schemes.OrderBase(
        id=order.id,
        order_time=format_datetime(order.order_time),
        status=order.status,
        user_id=order.user_id,
        table_number=order.table_number,
    )


@app.get("/orders", response_model=list[schemes.OrderBase], tags=["orders"])
def read_orders(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db),
):
    verify_role("staff", token, db)

    orders = db.query(Order).order_by(Order.order_time.desc()).all()
    return [
        schemes.OrderBase(
            id=order.id,
            order_time=format_datetime(order.order_time),
            status=order.status,
            user_id=order.user_id,
            table_number=order.table_number,
        )
        for order in orders
    ]


@app.post(
    "/orders/{order_id}/items", response_model=schemes.OrderItemPublic, tags=["orders"]
)
def create_order_item(
    order_id: int,
    form_data: schemes.OrderItemCreate,
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db),
):
    # verify_role("staff", token, db)

    order = db.query(Order).filter(Order.id == order_id).first()
    product = db.query(Product).filter(Product.id == form_data.product_id).first()

    if not order or not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Order or product not found."
        )

    new_order_item = OrderItem(
        order_id=order_id,
        product_id=form_data.product_id,
        quantity=form_data.quantity,
        ammount=form_data.quantity * product.price,
    )

    db.add(new_order_item)
    db.commit()

    new_order_item.set_local_order_time(region="America/Lima")
    db.commit()

    db.refresh(new_order_item)
    return schemes.OrderItemPublic(
        id=new_order_item.id,
        product=schemes.ProductPublic(
            id=new_order_item.product_id,
            name=new_order_item.product.name,
            description=new_order_item.product.description,
            price=new_order_item.product.price,
        ),
        order_time=format_datetime(new_order_item.order_time),
        quantity=new_order_item.quantity,
        ammount=new_order_item.ammount,
        status=new_order_item.status,
        paid=new_order_item.paid,
        order_id=new_order_item.order_id,
    )


@app.get(
    "/orders/{order_id}/items",
    response_model=list[schemes.OrderItemPublic],
    tags=["orders"],
)
def read_order_items(
    order_id: int,
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db),
):
    # verify_role("staff", token, db)

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Order not found."
        )

    order_items = (
        db.query(OrderItem)
        .filter(OrderItem.order_id == order_id)
        .order_by(OrderItem.order_time.desc())
        .all()
    )

    return [
        schemes.OrderItemPublic(
            id=order_item.id,
            product=schemes.ProductPublic(
                id=order_item.product_id,
                name=order_item.product.name,
                description=order_item.product.description,
                price=order_item.product.price,
            ),
            order_time=format_datetime(order_item.order_time),
            quantity=order_item.quantity,
            ammount=order_item.ammount,
            status=order_item.status,
            paid=order_item.paid,
            order_id=order_item.order_id,
        )
        for order_item in order_items
    ]
