from sqlalchemy import Column, Table, ForeignKey
from database import Base


FavoriteModel = Table(
    "movies_users",
    Base.metadata,
    Column(
        "movie_id",
        ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True,
        nullable=False),
    Column(
        "user_id",
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True,
        nullable=False),
)
