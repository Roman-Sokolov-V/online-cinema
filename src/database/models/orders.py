import enum
from datetime import datetime, UTC
from decimal import Decimal
from typing import List

from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
    DateTime,
    UniqueConstraint,
    DECIMAL,
    Enum
)

from database import Base
from database.models.accounts import UserModel
from database.models.movies import MovieModel


class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    CANCELED = "canceled"


class OrderItemModel(Base):
    __tablename__ = 'order_items'
    __table_args__ = (
        UniqueConstraint("order_id", "movie_id", name="uix_order_product"),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False
    )
    movie_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("movies.id", ondelete="CASCADE"),
        nullable=False
    )
    price_at_order: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=10, scale=2), nullable=False
    )
    movie: Mapped["MovieModel"] = relationship("MovieModel")

    def __repr__(self):
        return f"<OrderItemModel(id={self.id}, order_id={self.order_id}, movie_id={self.movie_id})>"


class OrderModel(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False
    )
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus), nullable=False, default=OrderStatus.PENDING
    )

    total_amount: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=10, scale=2), nullable=False
    )
    session_id: Mapped[str] = mapped_column(String, nullable=True)
    user: Mapped[UserModel] = relationship(
        UserModel, backref="orders", lazy="joined"
    )
    order_items: Mapped[List[OrderItemModel]] = relationship(
        OrderItemModel,
        backref="order", lazy="selectin", passive_deletes=True
    )
