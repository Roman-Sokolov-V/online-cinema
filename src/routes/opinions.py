from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from config import get_email_notificator
from database import (
    get_db, MovieModel, UserModel, CommentModel, RateModel
)
from notifications import EmailSenderInterface

from routes.filters import apply_m2m_filter

from routes.utils import get_required_access_token_payload
from schemas import (
    MovieListResponseSchema,
    MovieDetailSchema,
    AccessTokenPayload,
    ResponseMessageSchema,
    FavoriteListSchema, CommentSchema, ResponseCommentarySchema, ReplySchema,
    ResponseReplySchema
)
from schemas.opinions import RateSchema

router = APIRouter()


@router.post(
    "/movies/favorite/{movie_id}/",
    response_model=ResponseMessageSchema,
    summary="Add movie to favorite",
    description="<h3>Add specific movie to favorite list by id.</h3>",
    responses={
        201: {
            "description": "Movie successfully added to favorite list.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Movie successfully added to favorite list."}
                }
            },
        },
        404: {
            "description": "Movie not found.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Movie with the given ID was not found."}
                }
            },
        },
        400: {
            "description": "Movie already in favorite list.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Movie already in favorite list."}
                }
            },
        },

    },
    status_code=201
)
async def add_to_favorite(
        movie_id: int,
        db: AsyncSession = Depends(get_db),
        token_payload: AccessTokenPayload = Depends(
            get_required_access_token_payload)
) -> ResponseMessageSchema:
    stmt = select(MovieModel).where(MovieModel.id == movie_id)
    result = await db.execute(stmt)
    movie = result.scalars().first()
    if not movie:
        raise HTTPException(
            status_code=404,
            detail="Movie with the given ID was not found."
        )
    user_id = token_payload["user_id"]
    stmt = select(UserModel).where(UserModel.id == user_id).options(
        joinedload(UserModel.favorite_movies))
    result = await db.execute(stmt)
    user = result.scalars().first()

    if movie in user.favorite_movies:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Movie already in favorite list."
        )
    user.favorite_movies.append(movie)
    await db.commit()
    await db.refresh(user)
    return ResponseMessageSchema(
        detail="Movie successfully added to favorite list.")


@router.delete(
    "/movies/favorite/{movie_id}/",
    response_model=ResponseMessageSchema,
    summary="Remove movie from favorite list",
    description="<h3>Remove specific movie from favorite list by id.</h3>",
    responses={
        200: {
            "description": "Movie successfully removed from favorite list.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Movie successfully removed from favorite list."}
                }
            },
        },
        404: {
            "description": "Movie not found, or user not found",
            "content": {
                "application/json": {
                    "example": {
                        "movie_not_found": {
                            "detail": "Movie with the given ID was not found."
                        },
                        "user_not_found": {
                            "detail": "User with the access token was not found."
                        }
                    }

                }
            },
        },
        400: {
            "description": "Movie not found in favorite list.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Movie not found in favorite list."}
                }
            },
        },

    },
    status_code=200
)
async def remove_from_favorite(
        movie_id: int,
        db: AsyncSession = Depends(get_db),
        token_payload: AccessTokenPayload = Depends(
            get_required_access_token_payload)
) -> ResponseMessageSchema:
    stmt = select(MovieModel).where(MovieModel.id == movie_id)
    result = await db.execute(stmt)
    movie = result.scalars().first()

    if not movie:
        raise HTTPException(
            status_code=404,
            detail="Movie with the given ID was not found."
        )
    user_id = token_payload["user_id"]
    stmt = select(UserModel).where(UserModel.id == user_id).options(
        joinedload(UserModel.favorite_movies))
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User with the access token was not found."
        )

    if movie not in user.favorite_movies:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Movie not found in favorite list."
        )
    user.favorite_movies.remove(movie)
    await db.commit()
    return ResponseMessageSchema(
        detail="Movie successfully removed from favorite list.")


@router.get(
    "/movies/favorite/",
    summary="Retrieve favorite movie by id.",
    response_model=FavoriteListSchema,
    description=(
            "<h3>This endpoint retrieve favorite movie by id..</h3>"
    ),
    responses={
        404: {
            "description": "User with the access token was not found.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "User with the access token was not found."
                    }
                }
            },
        },
    },
)
async def get_favorites(
        token_payload: AccessTokenPayload = Depends(
            get_required_access_token_payload),
        db: AsyncSession = Depends(get_db),
        page: int = Query(1, ge=1, description="Page number (1-based index)"),
        per_page: int = Query(10, ge=1, le=20,
                              description="Number of items per page"),
        genres: Optional[str] = Query(
            default=None,
            description="Genres to filter on (single or muliiple with using '|' for OR, ',' for AND), Case-insensitive filtering.",
            examples=[
                "?genres=action|horror",
                "?genres=action,horror",
                "?genres=action"
            ],
            #example="action,horror"
        ),
        stars: str = Query(
            default=None,
            description="Stars to filter on (single or muliiple with using '|' for OR, ',' for AND), Case-insensitive filtering.",
            examples=[
                "?stars=Danny de Vito|Nicolas Cage",
                "?stars=Danny de Vito,Nicolas Cage",
                "?stars=Danny de Vito"
            ],
            example="Gaylen Ross,David Emge"
        ),
        directors: str = Query(
            default=None,
            description="Directors to filter on (single or muliiple with using '|' for OR, ',' for AND), Case-insensitive filtering.",
            examples=[
                "?directors=Stiven Spilberg|Nicolas Cage",
                "?directors=Stiven Spilberg,Nicolas Cage",
                "?directors=Stiven Spilberg"
            ],
            #example="George A. Romero"
        ),
        year: str = Query(
            default=None,
            description="Release  year to filter on (exact)",
            example="1978"
        ),
        min_rating: str = Query(
            default=None,
            description="IMDb rating to filter on. Biger or equal than value to filter on",
            example="7.8"
        ),
        sort_params: str = Query(
            default=None,
            description="Ordering movies by price: (l-price, h-price), or "
                        "release year: (older, newer) and imdb rating: rating"
                        "or a combination of them separated by a comma",
            examples={"single": {"value": "older"},
                      "multiple": {"value": "older,h-price"}},
            example="older,h-price"
        ),

) -> FavoriteListSchema:
    user_id = token_payload["user_id"]
    stmt = select(UserModel).where(UserModel.id == user_id)
    result = await db.execute(stmt)
    user = result.scalars().first()
    if user is None:
        if not user:
            raise HTTPException(
                status_code=404,
                detail="User with the access token was not found."
            )

    offset = (page - 1) * per_page

    stmt = select(MovieModel).where(
        MovieModel.users_like.any(UserModel.id == user.id)).options(
        selectinload(MovieModel.genres),
        selectinload(MovieModel.directors),
        selectinload(MovieModel.stars)
    )
    # stmt = select(UserModel.favorite_movies).where(UserModel.id == user_id).options(
    #     selectinload(UserModel.favorite_movies).selectinload(MovieModel.genres),
    #     selectinload(UserModel.favorite_movies).selectinload(MovieModel.directors),
    #     selectinload(UserModel.favorite_movies).selectinload(MovieModel.stars)
    # )

    stmt = apply_m2m_filter(stmt, MovieModel.genres, genres)
    stmt = apply_m2m_filter(stmt, MovieModel.directors, directors)
    stmt = apply_m2m_filter(stmt, MovieModel.stars, stars)

    if year:
        try:
            year = int(year)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="'year' in query string must be an integer."
            )
        stmt = stmt.filter(MovieModel.year == year)
    if min_rating:
        try:
            min_rating = float(min_rating)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="'min_rating' in query string must be a float."
            )
        stmt = stmt.filter(MovieModel.imdb >= min_rating)

    if sort_params:
        params = sort_params.split(",")
        allowed_params = {"l-price", "h-price", "older", "newer", "rating"}
        for index, param in enumerate(params):
            param = param.strip()
            if param not in allowed_params:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid sort_param value: '{param}', "
                           f"value should be one of {allowed_params}")
            params[index] = param

        if {"l-price", "h-price"}.issubset(params) or {"older",
                                                       "newer"}.issubset(
            params):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"opposite parameters as  cannot be in the same filter-set"
            )
        sort_map = {
            "l-price": MovieModel.price.asc,
            "h-price": MovieModel.price.desc,
            "older": MovieModel.year.asc,
            "newer": MovieModel.year.desc,
            "rating": MovieModel.imdb.desc
        }
        order_by = [sort_map[param]() for param in params]
        stmt = stmt.order_by(*order_by)
    count_filtered_stmt = select(func.count()).select_from(stmt.subquery())
    result_total_filtered_items = await db.execute(count_filtered_stmt)
    total_filtered_items = result_total_filtered_items.scalar() or 0

    stmt = stmt.offset(offset).limit(per_page)

    result_movies = await db.execute(stmt)
    movies = result_movies.scalars().all()

    movie_list = [MovieDetailSchema.model_validate(movie) for movie in movies]

    total_filtered_pages = (total_filtered_items + per_page - 1) // per_page

    response = MovieListResponseSchema(
        movies=movie_list,
        prev_page=f"/theater/movies/?page={page - 1}&per_page={per_page}" if page > 1 else None,
        next_page=f"/theater/movies/?page={page + 1}&per_page={per_page}" if page < total_filtered_pages else None,
        total_pages=total_filtered_pages,
        total_items=total_filtered_items,
    )
    return response


@router.post(
    "/movies/comment/{movie_id}/",
    response_model=ResponseCommentarySchema,
    summary="Add commentary",
    description="<h3>Add commentary to movie.</h3>",
    responses={
        201: {
            "description": "Comment successfully added to the movie.",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "content": "Nice movie!",
                        "user_id": 5,
                        "movie_id": 10,
                    }
                }
            },
        },
        404: {
            "description": "Movie not found.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Movie with the given ID was not found."}
                }
            },
        },
        400: {
            "description": "Movie is already commented.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "You already commented this movie"}
                }
            },
        },

    },
    status_code=201
)
async def add_comment_to_movie(
        movie_id: int,
        comment_data: CommentSchema,
        token_payload: AccessTokenPayload = Depends(
            get_required_access_token_payload),
        db: AsyncSession = Depends(get_db),

) -> ResponseCommentarySchema:
    user_id = token_payload["user_id"]
    movie = await db.get(MovieModel, movie_id)

    if movie is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found."
        )
    stmt = select(CommentModel.id).where(
        (CommentModel.user_id == user_id) &
        (CommentModel.movie_id == movie_id)
    )
    result = await db.execute(stmt)
    exists_comment = result.scalars().first()
    if exists_comment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already commented this movie"
        )

    comment = CommentModel(
        content=comment_data.content,
        user_id=user_id,
        movie_id=movie_id
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return ResponseCommentarySchema.model_validate(
        comment, from_attributes=True
    )


@router.post(
    "/movies/comment/reply/{comment_id}/",
    response_model=ResponseReplySchema,
    summary="Add commentary to movie",
    description="<h3>Add commentary to movie.</h3>",
    responses={
        201: {
            "description": "Reply successfully added to the movie.",
            "content": {
                "application/json": {
                    "example": {
                        "id": 100,
                        "content": "I totally agree!",
                        "user_id": 5,
                        "movie_id": 10,
                        "parent_id": 85
                    }
                }
            },
        },
        400: {
            "description": "You can't reply your commentary.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "You can't reply your commentary."}
                }
            },
        },
        404: {
            "description": "Commentary not found.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Commentary with the given ID was not found."}
                }
            },
        },
        422: {
            "description": "Validation Error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["body", "content"],
                                "msg": "Value error, At least one of content or is_like must be set",
                                "type": "value_error"
                            }
                        ]
                    }
                }
            },
        },
    },
    status_code=201
)
async def add_reply_to_comment(
        comment_id: int,
        reply_data: ReplySchema,
        token_payload: AccessTokenPayload = Depends(
            get_required_access_token_payload),
        db: AsyncSession = Depends(get_db),
        email_sender: EmailSenderInterface = Depends(
            get_email_notificator),
) -> ResponseCommentarySchema:
    user_id = token_payload["user_id"]

    stmt = select(CommentModel.movie_id).where(CommentModel.id == comment_id)
    result = await db.execute(stmt)
    movie_id = result.scalars().first()
    if movie_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Commentary not found."
        )
    stmt = select(MovieModel.name).where(MovieModel.id == movie_id)
    result = await db.execute(stmt)
    movie_title = result.scalars().first()

    comment = await db.get(CommentModel, comment_id)
    if comment.user_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You can't reply your commentary."
        )
    if comment.content is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You can't reply to commentary without content."
        )

    reply = CommentModel(
        content=reply_data.content,
        is_like=reply_data.is_like,
        user_id=user_id,
        movie_id=movie_id,
        parent_id=comment_id,
    )

    db.add(reply)
    await db.commit()
    await db.refresh(reply)

    recipient_user = await db.get(UserModel, comment.user_id)

    await email_sender.send_activity_notificator(
        email=recipient_user.email,
        comment_id=comment.id,
        comment_content=comment.content,
        reply_id=reply.id,
        is_like=reply.is_like,
        reply_content=reply.content,
        movie_title=movie_title
    )

    return ResponseReplySchema.model_validate(
        reply, from_attributes=True
    )


@router.post(
    "/movies/{movie_id}/rate",
    response_model=ResponseMessageSchema,
    summary="Rate movie",
    description="<h3>Rate movie by movie id. Estimation is an integer of 1 to 10</h3>",
    responses={
        200: {
            "description": "The film has been successfully appreciated",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Movie successfully rated.",
                    }
                }
            },
        },
        400: {
            "description": "Movie already rated. Can`t rate twice",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Movie already rated."}
                }
            },
        },
        404: {
            "description": "Movie not found.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Movie not found."}
                }
            },
        },
    },
    status_code=200
)
async def rate_movie(
        movie_id: int,
        data: RateSchema,
        token_payload: AccessTokenPayload = Depends(
            get_required_access_token_payload),
        db: AsyncSession = Depends(get_db),
) -> ResponseMessageSchema:
    movie = await db.get(MovieModel, movie_id)
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found."
        )
    user_id = token_payload["user_id"]
    stmt = select(RateModel).where(
        (RateModel.user_id == user_id) &
        (RateModel.movie_id == movie_id)
    )
    result = await db.execute(stmt)
    existing_rate = result.scalars().first()
    if existing_rate is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Movie already rated."
        )
    rate = RateModel(user_id=user_id, movie_id=movie_id, rate=data.rate)
    db.add(rate)
    await db.commit()
    return ResponseMessageSchema(detail="Movie successfully rated.")
