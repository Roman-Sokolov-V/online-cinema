from sqlalchemy import Column, Table, ForeignKey, Integer, UniqueConstraint
from database import Base


FavoriteModel = Table(
    "users_favorite_movies",
    Base.metadata,
    Column(
        "id", Integer,
        primary_key=True, autoincrement=True
    ),
    Column(
        "movie_id",
        ForeignKey("movies.id", ondelete="CASCADE"), nullable=False),
    Column(
        "user_id",
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    UniqueConstraint(
        "movie_id", "user_id", name="idx_unique_user_movie_favorite"
    ),
)
