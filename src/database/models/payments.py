import enum
from typing import List
from datetime import datetime, UTC
from decimal import Decimal

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, DateTime, Enum, DECIMAL, String
from sqlalchemy.sql.schema import ForeignKey

from database import Base, UserModel, OrderModel, OrderItemModel


class StatusPayment(str, enum.Enum):
    SUCCESSFUL = "successful"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class PaymentItemModel(Base):
    __tablename__ = "payment_items"
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    payment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("payments.id"), nullable=False
    )
    order_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("order_items.id"), nullable=False
    )
    price_at_payment: Mapped[Decimal] = mapped_column(
        DECIMAL(10, 2), nullable=False
    )
    order_item: Mapped["OrderItemModel"] = relationship(
        "OrderItemModel", backref="payment_items"
    )
    payment: Mapped["PaymentModel"] = relationship(
        "PaymentModel", back_populates="payment_items"
    )


class PaymentModel(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("orders.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False
    )
    status: Mapped[StatusPayment] = mapped_column(
        Enum(StatusPayment), nullable=False, default=StatusPayment.SUCCESSFUL
    )
    amount: Mapped[Decimal] = mapped_column(
        DECIMAL(10, 2), nullable=False, default=Decimal
    )
    external_payment_id: Mapped[str] = mapped_column(
        String, nullable=True
    )
    user: Mapped["UserModel"] = relationship(
        "UserModel", backref="payments"
    )
    order: Mapped["OrderModel"] = relationship(
        "OrderModel", backref="payments"
    )
    payment_items: Mapped[List[PaymentItemModel]] = relationship(
        PaymentItemModel, back_populates="payment", lazy="selectin"
    )
