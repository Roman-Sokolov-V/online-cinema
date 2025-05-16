from __future__ import annotations
import uuid
from sqlalchemy.types import Uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    String, Float, Text, DECIMAL, UniqueConstraint,
    ForeignKey, Table, Column, Integer
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import mapped_column, Mapped, relationship

from database import Base
from database.models.associations import FavoriteModel
from database.models.opinions import CommentModel


MoviesGenresModel = Table(
    "movies_genres",
    Base.metadata,
    Column(
        "movie_id",
        ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True,
        nullable=False),
    Column(
        "genre_id",
        ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True,
        nullable=False),
)


MoviesStarsModel = Table(
    "movies_stars",
    Base.metadata,
    Column(
        "movie_id", ForeignKey("movies.id"),
        primary_key=True, nullable=False
    ),
    Column(
        "star_id", ForeignKey("stars.id"),
        primary_key=True, nullable=False
    ),
)

MoviesDirectorsModel = Table(
    "movie_directors",
    Base.metadata,
    Column(
        "movie_id", ForeignKey("movies.id"),
        primary_key=True, nullable=False
    ),
    Column(
        "director_id", ForeignKey("directors.id"),
        primary_key=True, nullable=False
    ),
)


class GenreModel(Base):
    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    movies: Mapped[list[MovieModel]] = relationship(
        "MovieModel",
        secondary=MoviesGenresModel,
        back_populates="genres"
    )

    def __repr__(self):
        return f"<Genre(name='{self.name}')>"


class StarModel(Base):
    __tablename__ = "stars"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(unique=True, nullable=False)
    movies: Mapped[list[MovieModel]] = relationship(
        secondary=MoviesStarsModel,
        back_populates="stars"
    )

    def __repr__(self):
        return f"Stars id = {self.id}, name = {self.name}"


class DirectorModel(Base):
    __tablename__ = "directors"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    movies: Mapped[list[MovieModel]] = relationship(
        "MovieModel",
        secondary=MoviesDirectorsModel,
        back_populates="directors"
    )


class CertificationModel(Base):
    __tablename__ = "certification"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    movies: Mapped[list[MovieModel]] = relationship(back_populates="certification")


class MovieModel(Base):
    __tablename__ = "movies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    uuid: Mapped[Uuid] = mapped_column(
        UUID(as_uuid=True),
        default=uuid.uuid4,
        nullable=False,
        unique=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    time: Mapped[int] = mapped_column(Integer, nullable=False)
    imdb: Mapped[float] = mapped_column(Float, nullable=False)
    votes: Mapped[int] = mapped_column(Integer, nullable=False)
    meta_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gross: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    certification_id: Mapped[int] = mapped_column(
        ForeignKey("certification.id", ondelete="SET NULL"), nullable=True,
    )
    certification: Mapped[CertificationModel] = relationship(
        back_populates="movies",
        passive_deletes=True)
    genres: Mapped[list[GenreModel]] = relationship(
        "GenreModel",
        secondary=MoviesGenresModel,
        back_populates="movies"
    )
    stars: Mapped[list[StarModel]] = relationship(
        secondary=MoviesStarsModel,
        back_populates="movies"
    )
    directors: Mapped[list[DirectorModel]] = relationship(
        secondary=MoviesDirectorsModel,
        back_populates="movies"
    )
    comments: Mapped[list[CommentModel]] = relationship(
        CommentModel,
        backref="movie",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    users_like: Mapped[list["UserModel"]] = relationship(
        "UserModel",
        secondary=FavoriteModel,
        back_populates="favorite_movies"
    )
    __table_args__ = (
        UniqueConstraint(
            "name", "year", "time", name="unique_movie_constraint"
        ),
    )

    @classmethod
    def default_order_by(cls):
        return [cls.id.desc()]

    def __repr__(self):
        return (
            f"<Movie(name='{self.name}',"
            f" release_date='{self.year}',"
            f" score={self.meta_score})>"
        )

