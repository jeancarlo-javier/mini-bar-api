import schemes
import os
from typing import Annotated, Union
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from models import Base, Product, Order, OrderItem
from db import engine, get_db
from auth import authenticate_user, register_user, get_db_user_by_email
from jwtUtils import create_access_token, decode_and_verify_token
from datetime import datetime
from security import oauth2_scheme
from sqlalchemy import DateTime
from datetime import timedelta

load_dotenv()


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
    decoded = decode_and_verify_token(token)
    user = get_db_user_by_email(db, decoded["email"])
    if user.role != required_role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
        )


@app.get("/docs", dependencies=[Depends(oauth2_scheme)])
def custom_openapi():
    return {"msg": "Hello World"}


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
    form_data: schemes.UserCreate,
    db: Session = Depends(get_db),
):
    if form_data.secret.get_secret_value() != os.getenv("REGISTER_KEY"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
        )

    new_user = register_user(db, form_data)
    return schemes.UserBase(
        id=new_user.id,
        name=new_user.name,
        email=new_user.email,
        role=new_user.role,
    )


# User
@app.get("/me", response_model=schemes.UserBase, tags=["user"])
def read_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db),
):
    decoded = decode_and_verify_token(token)
    user = get_db_user_by_email(db, decoded["email"])

    return schemes.UserBase(
        id=user.id,
        name=user.name,
        role=user.role,
        email=user.email,
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
    decode_and_verify_token(token)
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
    decode_and_verify_token(token)

    products = db.query(Product).order_by(Product.name.asc()).all()

    return [
        schemes.ProductPublic(
            id=product.id,
            name=product.name,
            description=product.description,
            price=product.price,
            archived=product.archived,
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
@app.post("/orders", response_model=schemes.OrderBase, tags=["orders"], status_code=201)
def create_order(
    form_data: schemes.OrderCreate,
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db),
):
    decoded = decode_and_verify_token(token)

    order = Order(
        user_id=decoded["sub"],
        status="pending",
        table_number=form_data.table_number,
    )
    db.add(order)
    db.commit()

    order.set_local_order_time(region="America/Lima")
    order.set_last_order_time(region="America/Lima")
    db.commit()

    db.refresh(order)

    return schemes.OrderBase(
        id=order.id,
        status=order.status,
        order_time=format_datetime(order.order_time),
        last_order_time=format_datetime(order.last_order_time),
        note=order.note,
        user=schemes.UserBase(
            id=order.user_id,
            name=order.user.name,
            role=order.user.role,
            email=order.user.email,
        ),
        table_number=order.table_number,
        total=order.total,
    )


@app.get("/orders/{order_id}", response_model=schemes.OrderBase, tags=["orders"])
def read_order(
    order_id: int,
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db),
):
    decode_and_verify_token(token)

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Order not found."
        )

    return schemes.OrderBase(
        id=order.id,
        status=order.status,
        order_time=format_datetime(order.order_time),
        last_order_time=format_datetime(order.last_order_time),
        note=order.note,
        user=schemes.UserBase(
            id=order.user_id,
            name=order.user.name,
            role=order.user.role,
            email=order.user.email,
        ),
        table_number=order.table_number,
        total=order.total,
    )


@app.get("/orders", response_model=list[schemes.OrderBase], tags=["orders"])
def read_orders(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db),
):
    decode_and_verify_token(token)

    orders = (
        db.query(Order)
        .order_by(Order.last_order_time.desc())
        .filter(Order.order_time >= datetime.now() - timedelta(hours=12))
        .all()
    )

    return [
        schemes.OrderBase(
            id=order.id,
            status=order.status,
            order_time=format_datetime(order.order_time),
            last_order_time=format_datetime(order.last_order_time),
            note=order.note,
            user=schemes.UserBase(
                id=order.user_id,
                name=order.user.name,
                role=order.user.role,
                email=order.user.email,
            ),
            table_number=order.table_number,
            total=order.total,
        )
        for order in orders
    ]


@app.patch(
    "/orders/{order_id}/complete",
    tags=["orders"],
)
def complete_order(
    order_id: int,
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db),
):
    decode_and_verify_token(token)
    order = db.query(Order).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Order not found."
        )

    if order.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order is not pending, can't be completed.",
        )

    for item in order.items:
        if item.status == "canceled":
            continue
        elif item.status != "attended" or not item.paid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Order is not complete, can't be completed.",
            )

    order.status = "completed"
    db.commit()

    return {"message": "Order was completed successfully"}


# Order Items
@app.post(
    "/orders/{order_id}/items",
    response_model=list[schemes.OrderItemPublic],
    tags=["order-items"],
    status_code=201,
)
def add_items_to_order(
    order_id: int,
    items: list[schemes.OrderItemCreate],
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db),
):
    decode_and_verify_token(token)

    # Fetch the order once and validate
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found.",
        )

    result_items = []

    for item in items:
        product = db.query(Product).filter(Product.id == item.product_id).first()

        # Validate product
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product with id {item.product_id} not found.",
            )

        # Create new order item
        new_order_item = OrderItem(
            order_id=order_id,
            product_id=item.product_id,
            quantity=item.quantity,
            amount=item.quantity * product.price,
        )

        db.add(new_order_item)

        # Update order totals and times
        new_order_item.set_local_order_time(region="America/Lima")
        order.set_last_order_time(region="America/Lima")
        order.total += new_order_item.amount

        # Commit and refresh order item
        db.commit()
        db.refresh(new_order_item)

        # Append the result to the list
        result_items.append(
            schemes.OrderItemPublic(
                id=new_order_item.id,
                product=schemes.ProductPublic(
                    id=new_order_item.product_id,
                    name=new_order_item.product.name,
                    description=new_order_item.product.description,
                    price=new_order_item.product.price,
                    archived=new_order_item.product.archived,
                ),
                order_time=format_datetime(new_order_item.order_time),
                quantity=new_order_item.quantity,
                amount=new_order_item.amount,
                status=new_order_item.status,
                paid=new_order_item.paid,
                order_id=new_order_item.order_id,
            )
        )

    return result_items


@app.get(
    "/orders/{order_id}/items",
    response_model=list[schemes.OrderItemPublic],
    tags=["order-items"],
)
def read_order_items(
    order_id: int,
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db),
):
    decode_and_verify_token(token)

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
                archived=order_item.product.archived,
            ),
            order_time=format_datetime(order_item.order_time),
            quantity=order_item.quantity,
            amount=order_item.amount,
            status=order_item.status,
            paid=order_item.paid,
            order_id=order_item.order_id,
        )
        for order_item in order_items
    ]


@app.patch(
    "/items/{item_id}/toggle-status",
    tags=["order-items"],
)
def toggle_order_item_status(
    item_id: int,
    form_data: schemes.OrderItemToggleStatus,
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db),
):
    decode_and_verify_token(token)

    status_to_toggle = form_data.status

    order_item = db.query(OrderItem).filter(OrderItem.id == item_id).first()
    if not order_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order item not found.",
        )

    if status_to_toggle == "item_payment_status":
        order_item.paid = not order_item.paid
    elif status_to_toggle == "item_status":
        if order_item.status == "pending":
            order_item.status = "attended"
        elif order_item.status == "attended":
            order_item.status = "pending"
        elif order_item.status == "canceled":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Order Canceled, can't be changed.",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid status to toggle.",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid status to toggle.",
        )

    db.commit()

    return {"message": "Order item status was updated successfully"}


@app.patch("/items/{item_id}/cancel", tags=["order-items"])
def cancel_order_item(
    item_id: int,
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db),
):
    decode_and_verify_token(token)

    order_item = db.query(OrderItem).filter(OrderItem.id == item_id).first()
    if not order_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order item not found.",
        )

    if order_item.status == "attended" or order_item.paid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order item was attended or paid, can't be canceled.",
        )

    order_item.order.total -= order_item.amount
    order_item.status = "canceled"
    db.commit()

    return {"message": "Order item was canceled successfully"}
