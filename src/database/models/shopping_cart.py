from datetime import datetime
from typing import List

from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy import ForeignKey, Integer, DateTime, func, UniqueConstraint

from database import Base
from .accounts import UserModel
from .movies import MovieModel


class CartItemModel(Base):
    __tablename__ = 'cart_items'
    __table_args__ = (
        UniqueConstraint("cart_id", "movie_id", name="uix_cart_product"),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, auto_increment=True
    )
    cart_id: Mapped[int] = mapped_column(
        Integer, ForeignKey('shopping_cart.id'), nullable=False
    )
    movie_id: Mapped[int] = mapped_column(
        Integer, ForeignKey('movies.id'), nullable=False
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    movie: Mapped["MovieModel"] = relationship("MovieModel", lazy="joined")

    def __repr__(self):
        return f"<CartItemModel(id={self.id}, cart_id={self.cart_id}, movie_id={self.movie_id})>"


class CartModel(Base):
    __tablename__ = "shopping_cart"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, auto_increment=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )
    user: Mapped[UserModel] = relationship(
        UserModel, backref="cart", lazy="joined"
    )
    cart_items: Mapped[List[CartItemModel]] = relationship(
        CartItemModel,
        backref="cart", lazy="joined", cascade="all, delete-orphan"
    )


class PurchaseModel(Base):
    __tablename__ = 'purchases'
    __table_args__ = (
        UniqueConstraint(
            "user_id", "movie_id", name="uix_purchase_product"
        ),
    )
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, auto_increment=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"), nullable=False
    )
    movie_id: Mapped[int] = mapped_column(
        Integer, ForeignKey('movies.id'), nullable=False
    )
    purchase_date: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    user: Mapped[UserModel] = relationship(
        UserModel, backref="purchases", lazy="joined"
    )
    movie: Mapped[MovieModel] = relationship(MovieModel)
