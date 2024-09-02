from sqlalchemy import func, text
from pytz import timezone
from sqlalchemy import (
    Integer,
    String,
    Boolean,
    Numeric,
    ForeignKey,
    Enum,
    DateTime,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from datetime import datetime
import pytz


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(
        Enum("staff", "admin", name="user_roles"), nullable=False
    )
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)

    orders: Mapped[list["Order"]] = relationship(back_populates="user")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String(2000), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    production_cost: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_time: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    last_order_time: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    status: Mapped[str] = mapped_column(
        Enum("pending", "completed", "canceled", name="order_statuses"),
        default="pending",
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    table_number: Mapped[int] = mapped_column(Integer, nullable=False)

    user: Mapped["User"] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order")

    def set_local_order_time(self, region="America/Lima"):
        tz = pytz.timezone(region)
        self.order_time = datetime.now(tz)

    def set_last_order_time(self, region="America/Lima"):
        tz = pytz.timezone(region)
        self.last_order_time = datetime.now(tz)


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("orders.id"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id"), nullable=False
    )
    order_time: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    ammount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(
            "pending",
            "completed",
            "canceled",
            name="item_statuses",
        ),
        default="pending",
        nullable=False,
    )
    paid: Mapped[bool] = mapped_column(Boolean, default=False)

    order: Mapped["Order"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()

    def set_local_order_time(self, region="America/Lima"):
        tz = pytz.timezone(region)
        self.order_time = datetime.now(tz)
