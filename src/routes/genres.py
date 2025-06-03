from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, GenreModel, MoviesGenresModel, MovieModel
from routes.permissions import is_moderator_or_admin
from schemas import (
    GenreCreateSchema,
    GenreSchema,
    GenreListSchema,
    GenreExtendSchema,
    MovieBaseSchema,
    MoviesRelatedGenresSchema,
)


router = APIRouter()


@router.post(
    "/genres/",
    dependencies=[Depends(is_moderator_or_admin)],
    response_model=GenreSchema,
    summary="Create a genre",
    description=(
        "This endpoint allows moderators and admins to add a genres"
        " to the database."
    ),
    responses={
        201: {
            "description": "The genre has been created",
        },
        409: {
            "description": "Invalid input.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Genre with given name already exists."
                    }
                }
            },
        },
        403: {
            "description": (
                "Request user do not has permissions to use this "
                "endpoint. Only admins and moderators can add genres."
            ),
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Access denied, not enough permissions"
                    }
                }
            },
        },
    },
    status_code=201,
)
async def create_genre(
    genre_data: GenreCreateSchema, db: AsyncSession = Depends(get_db)
) -> GenreSchema:
    genre = await db.scalar(
        select(GenreModel).where(GenreModel.name == genre_data.name)
    )
    if genre:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Genre with given name already exists.",
        )
    genre = GenreModel(**genre_data.model_dump())
    db.add(genre)
    await db.commit()
    await db.refresh(genre)
    return GenreSchema.model_validate(genre)


@router.get(
    "/genres/",
    response_model=GenreListSchema,
    summary="Get list of genres",
    description=(
        "<h3>This endpoint allows all users to get a list of genres.</h3>"
    ),
    status_code=200,
)
async def get_genres(db: AsyncSession = Depends(get_db)) -> GenreListSchema:
    stmt = (
        select(
            GenreModel.id,
            GenreModel.name,
            func.count(MovieModel.id).label("number_of_movies"),
        )
        .outerjoin(
            MoviesGenresModel, GenreModel.id == MoviesGenresModel.c.genre_id
        )
        .outerjoin(MovieModel, MoviesGenresModel.c.movie_id == MovieModel.id)
        .group_by(GenreModel.id)
    )
    result = await db.execute(stmt)
    rows = result.fetchall()
    genres_list = [GenreExtendSchema.model_validate(row) for row in rows]

    return GenreListSchema(genres=genres_list)


@router.delete(
    "/genres/{genre_id}/",
    dependencies=[Depends(is_moderator_or_admin)],
    summary="Delete a genre",
    description=(
        "<h3>Delete a specific genre from the database by its unique ID.</h3>"
        "<p>If the genre exists, it will be deleted. If it does not exist, "
        "a 404 error will be returned.</p>"
    ),
    responses={
        204: {
            "description": "Genre deleted successfully.",
        },
        404: {
            "description": "Genre not found.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Genre with the given ID was not found."
                    }
                }
            },
        },
        403: {
            "description": (
                "Request user do not has permissions to use this "
                "endpoint. Only admins and moderators can add genres."
            ),
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Access denied, not enough permissions"
                    }
                }
            },
        },
    },
    status_code=204,
)
async def delete_genre(genre_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(GenreModel).where(GenreModel.id == genre_id)
    result = await db.execute(stmt)
    genre = result.scalars().first()

    if not genre:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Genre with the given ID was not found.",
        )
    await db.delete(genre)
    await db.commit()
    return {"detail": "Genre deleted successfully."}


@router.patch(
    "/genres/{genre_id}/",
    dependencies=[Depends(is_moderator_or_admin)],
    summary="Update a genre",
    description=(
        "<h3>Update a specific genre from the database by its unique ID.</h3>"
    ),
    responses={
        200: {
            "description": "Genre updated successfully.",
            "content": {
                "application/json": {
                    "example": {"detail": "Genre updated successfully."}
                }
            },
        },
        404: {
            "description": "Genre with the given ID was not found.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Genre with the given ID was not found."
                    }
                }
            },
        },
        409: {
            "description": "Invalid input.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Genre with given name already exists."
                    }
                }
            },
        },
        403: {
            "description": (
                "Request user do not has permissions to use this "
                "endpoint. Only admins and moderators can add genres."
            ),
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Access denied, not enough permissions"
                    }
                }
            },
        },
    },
    status_code=200,
)
async def update_genre(
    genre_id: int,
    genre_data: GenreCreateSchema,
    db: AsyncSession = Depends(get_db),
) -> GenreSchema:
    stmt = select(GenreModel).where(GenreModel.name == genre_data.name)
    result = await db.execute(stmt)
    genre_with_given_new_name = result.scalars().first()
    if genre_with_given_new_name:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Genre with given name already exists.",
        )

    genre = await db.scalar(
        select(GenreModel).where(GenreModel.id == genre_id)
    )
    if not genre:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Genre with the given ID was not found.",
        )
    genre.name = genre_data.name
    await db.commit()
    await db.refresh(genre)

    return GenreSchema.model_validate(genre)


@router.get(
    "/genres/{genre_id}/",
    response_model=MoviesRelatedGenresSchema,
    summary="Retrieve all related with genre movie",
    description=(
        "<h3>Retrieve all related with genre movie by genre unique ID.</h3>"
    ),
    responses={
        404: {
            "description": "Genre not found.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Genre with the given ID was not found."
                    }
                }
            },
        },
    },
    status_code=200,
)
async def get_related_movies(
    genre_id: int, db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(GenreModel)
        .where(GenreModel.id == genre_id)
        .options(joinedload(GenreModel.movies))
    )
    result = await db.execute(stmt)
    genre = result.scalars().first()
    if not genre:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Genre with the given ID was not found.",
        )
    movies_list = [
        MovieBaseSchema.model_validate(movie) for movie in genre.movies
    ]
    return MoviesRelatedGenresSchema(movies=movies_list)
