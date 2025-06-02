from datetime import date
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field

from schemas.examples.movies import (
    genre_schema_example,
    star_schema_example,
    movie_item_schema_example,
    movie_list_response_schema_example,
    movie_create_schema_example,
    movie_detail_schema_example,
    movie_update_schema_example,
    director_schema_example,
    genre_create_schema_example,
    genre_list_schema_example,
    star_create_schema_example,
    star_list_schema_example,
    genre_extend_schema_example
)


class GenreCreateSchema(BaseModel):
    name: str

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                genre_create_schema_example
            ]
        }
    }


class GenreSchema(BaseModel):
    id: int
    name: str

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                genre_schema_example
            ]
        }
    }


class GenreExtendSchema(GenreSchema):
    number_of_movies: int

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                genre_extend_schema_example
            ]
        }
    }


class GenreListSchema(BaseModel):
    genres: List[GenreExtendSchema]

    model_config = {
        "json_schema_extra": {
            "examples": [
                genre_list_schema_example
            ]
        }
    }


class StarCreateSchema(BaseModel):
    name: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                star_create_schema_example
            ]
        }
    }


class StarSchema(BaseModel):
    id: int
    name: str

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                star_schema_example
            ]
        }
    }


class StarListSchema(BaseModel):
    stars: List[StarSchema]

    model_config = {
        "json_schema_extra": {
            "examples": [
                star_list_schema_example
            ]
        }
    }


class DirectorSchema(BaseModel):
    id: int
    name: str

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                director_schema_example
            ]
        }
    }


class MovieBaseSchema(BaseModel):
    name: str
    uuid: UUID
    year: int = Field(..., ge=1888, le=date.today().year)
    time: int
    imdb: float = Field(..., ge=1.0, le=10.0)
    votes: int = Field(..., ge=1)
    meta_score: Optional[float] = Field(None, ge=0.0)
    gross: Optional[float] = Field(None, ge=0.0)
    description: str
    price: Decimal = Field(..., ge=0, le=Decimal("99999999.99"))
    certification_id: int

    model_config = {
        "from_attributes": True
    }


class MovieDetailSchema(MovieBaseSchema):
    id: int
    genres: List[GenreSchema]
    stars: List[StarSchema]
    directors: List[DirectorSchema]

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                movie_detail_schema_example
            ]
        }
    }


class MovieListItemSchema(MovieBaseSchema):
    id: int
    genres: List[GenreSchema]
    stars: List[StarSchema]
    directors: List[DirectorSchema]

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                movie_item_schema_example
            ]
        }
    }


class MovieListResponseSchema(BaseModel):
    movies: List[MovieListItemSchema]
    prev_page: Optional[str]
    next_page: Optional[str]
    total_pages: int
    total_items: int

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                movie_list_response_schema_example
            ]
        }
    }


class MovieCreateSchema(BaseModel):
    name: str
    year: int = Field(..., ge=1888, le=date.today().year)
    time: int
    imdb: float = Field(..., ge=1.0, le=10.0)
    votes: int = Field(..., ge=1)
    meta_score: Optional[float] = Field(None, ge=0.0)
    gross: Optional[float] = Field(None, ge=0.0)
    description: str
    price: Decimal = Field(..., ge=0, le=Decimal("99999999.99"))
    certification_name: str
    genres: Optional[List[str]] = None
    stars: Optional[List[str]] = None
    directors: Optional[List[str]] = None

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                movie_create_schema_example
            ]
        }
    }


class MovieUpdateSchema(BaseModel):
    name: Optional[str] = None
    year: Optional[int] = Field(None, ge=1888, le=date.today().year)
    time: Optional[int] = None
    imdb: Optional[float] = Field(None, ge=1.0, le=10.0)
    votes: Optional[int] = Field(None, ge=1)
    meta_score: Optional[float] = Field(None, ge=0.0)
    gross: Optional[float] = Field(None, ge=0.0)
    description: Optional[str] = None
    price: Optional[Decimal] = Field(None, ge=0, le=Decimal("99999999.99"))
    certification_name: Optional[str] = None
    genres: Optional[List[str]] = None
    stars: Optional[List[str]] = None
    directors: Optional[List[str]] = None

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                movie_update_schema_example
            ]
        }
    }


class MoviesRelatedGenresSchema(BaseModel):
    movies: List[MovieBaseSchema]


class ResponseMessageSchema(BaseModel):
    detail: str


class FavoriteListSchema(BaseModel):
    movies: List[MovieListItemSchema]
