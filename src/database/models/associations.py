from sqlalchemy import Column, Table, ForeignKey, Integer, String, UniqueConstraint, CheckConstraint
from database import Base


FavoriteModel = Table(
    "movies_users",
    Base.metadata,
    Column(
        "id", Integer,
        primary_key=True, autoincrement=True, nullable=False
    ),
    Column(
        "movie_id",
        ForeignKey("movies.id", ondelete="CASCADE"), nullable=False),
    Column(
        "user_id",
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column(
        "rate", Integer, nullable=True,
    ),
    UniqueConstraint(
        "movie_id", "user_id", name="idx_unique_user_movie"
    ),
    CheckConstraint("rate BETWEEN 1 AND 10", name="check_rate_range")
)
