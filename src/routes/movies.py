from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from database import (
    get_db, MovieModel, StarModel, DirectorModel, CertificationModel
)
from database import GenreModel
from routes.filters import apply_m2m_filter
from routes.permissions import is_moderator_or_admin
from schemas import (
    MovieListResponseSchema,
    MovieDetailSchema,
    MovieUpdateSchema,
    MovieCreateSchema
)


router = APIRouter()


@router.get(
    "/movies/",
    response_model=MovieListResponseSchema,
    summary="Get a paginated list of movies",
    description=(
            "<h3>This endpoint retrieves a paginated list of movies from the database.</h3>"
    "<ul>"
    "<li>Use <code>page</code> and <code>per_page</code> to paginate results.</li>"
    "<li>Filter movies by <code>genres</code>, <code>stars</code>, <code>directors</code>, <code>year</code>, and <code>min_rating</code>.</li>"
    "<li>Sort results using <code>sort_params</code> (e.g., <code>older,rating</code>). Only non-conflicting combinations are allowed.</li>"
    "</ul>"
    "<p>Example: <code>/movies/?genres=action,horror&sort_params=older,rating&page=2</code></p>"
    ),
    responses={
        404: {
            "description": "No movies found.",
            "content": {
                "application/json": {
                    "example": {"detail": "No movies found."}
                }
            },
        }
    }
)
async def get_movie_list(
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
            example="action,horror"
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
            example="George A. Romero"
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
            examples={"single": {"value": "older"}, "multiple": {"value": "older,h-price"}},
            example="older,h-price"
        ),

        db: AsyncSession = Depends(get_db),
) -> MovieListResponseSchema:
    """
    Retrieve a paginated and filterable list of movies from the database.

    This endpoint allows clients to query movies with flexible filtering and sorting options.
    Clients can specify pagination (`page`, `per_page`), and apply filters on genres, stars,
    directors, release year, and minimum IMDb rating. Sorting can be applied on price,
    release year, and rating.

    Filtering:
    - `genres`, `stars`, `directors`: support multiple values using:
        - `,` for AND (e.g., `action,comedy`)
        - `|` for OR  (e.g., `action|horror`)
    - `year`: filter by exact release year (e.g., `1978`)
    - `min_rating`: float, filters movies with IMDb rating >= value

    Sorting (`sort_params`):
    - Use comma-separated values. Supported options:
        - `l-price`: price low to high
        - `h-price`: price high to low
        - `older`: oldest movies first
        - `newer`: newest movies first
        - `rating`: IMDb rating descending
    - Conflicting options are not allowed together, e.g.:
        - `l-price` and `h-price`
        - `older` and `newer`

    Parameters:
    - page (int): Page number to retrieve (starting from 1).
    - per_page (int): Number of movies per page (1 to 20).
    - genres (str, optional): Filter by genres.
    - stars (str, optional): Filter by stars.
    - directors (str, optional): Filter by directors.
    - year (str, optional): Filter by exact release year.
    - min_rating (str, optional): Filter by minimum IMDb rating.
    - sort_params (str, optional): Sorting parameters (see above).

    Returns:
    - MovieListResponseSchema: Paginated list of movies with navigation links and metadata.

    Raises:
    - HTTPException 400: For invalid filters, sort parameters, or types.
    - HTTPException 404: If no movies match the filters.
    """

    offset = (page - 1) * per_page
    if not sort_params:
        order_by = MovieModel.default_order_by()
    else:
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

        if {"l-price", "h-price"}.issubset(params) or {"older", "newer"}.issubset(params):
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

    stmt = select(MovieModel).options(
        selectinload(MovieModel.genres),
        selectinload(MovieModel.directors),
        selectinload(MovieModel.stars)
    )

    stmt = apply_m2m_filter(stmt, MovieModel.genres, genres)
    stmt = apply_m2m_filter(stmt, MovieModel.directors, directors)
    stmt = apply_m2m_filter(stmt, MovieModel.stars, stars)

    if year:
        try:
            print(year)
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

    if order_by:
        stmt = stmt.order_by(*order_by)

    count_filtered_stmt = select(func.count()).select_from(stmt.subquery())
    result_total_filtered_items = await db.execute(count_filtered_stmt)
    total_filtered_items = result_total_filtered_items.scalar() or 0

    stmt = stmt.offset(offset).limit(per_page)

    result_movies = await db.execute(stmt)
    movies = result_movies.scalars().all()

    if not movies:
        raise HTTPException(status_code=404, detail="No movies found.")

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
    "/movies/",
    dependencies=[Depends(is_moderator_or_admin)],
    response_model=MovieDetailSchema,
    summary="Add a new movie",
    description=(
            "<h3>This endpoint allows moderators and admins add a new movie to the database. "
            "It accepts details such as name, year, genres, stars, imdb, and "
            "other attributes. The associated stars, directors and genres "
            "will be created or linked automatically.</h3>"
    ),
    responses={
        201: {
            "description": "Movie created successfully.",
        },
        400: {
            "description": "Invalid input.",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid input data."}
                }
            },
        }
    },
    status_code=201
)
async def create_movie(
        movie_data: MovieCreateSchema,
        db: AsyncSession = Depends(get_db)
) -> MovieDetailSchema:
    """
    Add a new movie to the database.

    This endpoint allows moderators and admins add a new movie to the database
     with details such as name, year, genres, stars, imdb, time, votes,
    meta_score, gross, description, price, certification, genres, stars,
    directors. It automatically handles linking or creating related entities.

    :param movie_data: The data required to create a new movie.
    :type movie_data: MovieCreateSchema
    :param db: The SQLAlchemy async database session (provided via dependency injection).
    :type db: AsyncSession

    :return: The created movie with all details.
    :rtype: MovieDetailSchema

    :raises HTTPException:
        - 409 if a movie with the same name and date already exists.
        - 400 if input data is invalid (e.g., violating a constraint).
    """
    existing_stmt = select(MovieModel).where(
        (MovieModel.name == movie_data.name) &
        (MovieModel.year == movie_data.year) &
        (MovieModel.time == movie_data.time)
    )
    existing_result = await db.execute(existing_stmt)
    existing_movie = existing_result.scalars().first()

    if existing_movie:
        raise HTTPException(
            status_code=409,
            detail=(
                f"A movie with the name '{movie_data.name}', release year "
                f"'{movie_data.year}' and duration time '{movie_data.time}' "
                f"already exists."
            )
        )

    try:
        genres = []
        if movie_data.genres:
            for genre_name in movie_data.genres:
                genre_stmt = select(GenreModel).where(
                    GenreModel.name == genre_name)
                genre_result = await db.execute(genre_stmt)
                genre = genre_result.scalars().first()

                if not genre:
                    genre = GenreModel(name=genre_name)
                    db.add(genre)
                    await db.flush()
                genres.append(genre)
        stars = []
        if movie_data.stars:
            for star_name in movie_data.stars:
                star_stmt = select(StarModel).where(
                    StarModel.name == star_name)
                star_result = await db.execute(star_stmt)
                star = star_result.scalars().first()

                if not star:
                    star = StarModel(name=star_name)
                    db.add(star)
                    await db.flush()
                stars.append(star)

        directors = []
        if movie_data.directors:
            for director_name in movie_data.directors:
                director_stmt = select(DirectorModel).where(
                    DirectorModel.name == director_name)
                director_result = await db.execute(director_stmt)
                director = director_result.scalars().first()

                if not director:
                    director = DirectorModel(name=director_name)
                    db.add(director)
                    await db.flush()
                directors.append(director)

        certification_stmt = select(CertificationModel).where(
            (CertificationModel.name == movie_data.certification_name)
        )
        certification_result = await db.execute(certification_stmt)
        certification = certification_result.scalars().first()
        if not certification:
            certification = CertificationModel(
                name=movie_data.certification_name)

        movie = MovieModel(
            name=movie_data.name,
            year=movie_data.year,
            time=movie_data.time,
            imdb=movie_data.imdb,
            votes=movie_data.votes,
            meta_score=movie_data.meta_score,
            gross=movie_data.gross,
            description=movie_data.description,
            price=movie_data.price,
            certification=certification,
            genres=genres,
            stars=stars,
            directors=directors
        )

        db.add(movie)
        await db.commit()
        await db.refresh(
            movie,
            ["genres", "stars", "directors", "certification"]
        )

        return MovieDetailSchema.model_validate(movie)

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")


@router.get(
    "/movies/{movie_id}/",
    response_model=MovieDetailSchema,
    summary="Get movie details by ID",
    description=(
            "<h3>Fetch detailed information about a specific movie by its unique ID. "
            "This endpoint retrieves all available details for the movie, such as "
            "its name, genre, crew, budget, and revenue. If the movie with the given "
            "ID is not found, a 404 error will be returned.</h3>"
    ),
    responses={
        404: {
            "description": "Movie not found.",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie with the given ID was not found."}
                }
            },
        }
    }
)
async def get_movie_by_id(
        movie_id: int,
        db: AsyncSession = Depends(get_db),
) -> MovieDetailSchema:
    """
    Retrieve detailed information about a specific movie by its ID.

    This function fetches detailed information about a movie identified by its unique ID.
    If the movie does not exist, a 404 error is returned.

    :param movie_id: The unique identifier of the movie to retrieve.
    :type movie_id: int
    :param db: The SQLAlchemy database session (provided via dependency injection).
    :type db: AsyncSession

    :return: The details of the requested movie.
    :rtype: MovieDetailResponseSchema

    :raises HTTPException: Raises a 404 error if the movie with the given ID is not found.
    """
    stmt = (
        select(MovieModel)
        .options(
            joinedload(MovieModel.directors),
            joinedload(MovieModel.genres),
            joinedload(MovieModel.stars),
        )
        .where(MovieModel.id == movie_id)
    )

    result = await db.execute(stmt)
    movie = result.scalars().first()

    if not movie:
        raise HTTPException(
            status_code=404,
            detail="Movie with the given ID was not found."
        )

    return MovieDetailSchema.model_validate(movie)


@router.delete(
    "/movies/{movie_id}/",
    dependencies=[Depends(is_moderator_or_admin)],
    summary="Delete a movie by ID",
    description=(
            "<h3>Delete a specific movie from the database by its unique ID.</h3>"
            "<p>If the movie exists, it will be deleted. If it does not exist, "
            "a 404 error will be returned.</p>"
    ),
    responses={
        204: {
            "description": "Movie deleted successfully."
        },
        404: {
            "description": "Movie not found.",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie with the given ID was not found."}
                }
            },
        },
    },
    status_code=204
)
async def delete_movie(
        movie_id: int,
        db: AsyncSession = Depends(get_db),
):
    """
    Delete a specific movie by its ID.

    This function deletes a movie identified by its unique ID.
    If the movie does not exist, a 404 error is raised.

    :param movie_id: The unique identifier of the movie to delete.
    :type movie_id: int
    :param db: The SQLAlchemy database session (provided via dependency injection).
    :type db: AsyncSession

    :raises HTTPException: Raises a 404 error if the movie with the given ID is not found.

    :return: A response indicating the successful deletion of the movie.
    :rtype: None
    """
    stmt = select(MovieModel).where(MovieModel.id == movie_id)
    result = await db.execute(stmt)
    movie = result.scalars().first()

    if not movie:
        raise HTTPException(
            status_code=404,
            detail="Movie with the given ID was not found."
        )

    await db.delete(movie)
    await db.commit()

    return {"detail": "Movie deleted successfully."}


@router.patch(
    "/movies/{movie_id}/",
    dependencies=[Depends(is_moderator_or_admin)],
    summary="Update a movie by ID",
    description=(
            "<h3>Update details of a specific movie by its unique ID.</h3>"
            "<p>This endpoint updates the details of an existing movie. If the movie with "
            "the given ID does not exist, a 404 error is returned.</p>"
    ),
    responses={
        200: {
            "description": "Movie updated successfully.",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie updated successfully."}
                }
            },
        },
        404: {
            "description": "Movie not found.",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie with the given ID was not found."}
                }
            },
        },
    }
)
async def update_movie(
        movie_id: int,
        movie_data: MovieUpdateSchema,
        db: AsyncSession = Depends(get_db),
):
    """
    Update a specific movie by its ID.

    This function updates a movie identified by its unique ID.
    If the movie does not exist, a 404 error is raised.

    :param movie_id: The unique identifier of the movie to update.
    :type movie_id: int
    :param movie_data: The updated data for the movie.
    :type movie_data: MovieUpdateSchema
    :param db: The SQLAlchemy database session (provided via dependency injection).
    :type db: AsyncSession

    :raises HTTPException: Raises a 404 error if the movie with the given ID is not found.

    :return: A response indicating the successful update of the movie.
    :rtype: None
    """
    stmt = select(MovieModel).where(MovieModel.id == movie_id)
    result = await db.execute(stmt)
    movie = result.scalars().first()

    if not movie:
        raise HTTPException(
            status_code=404,
            detail="Movie with the given ID was not found."
        )

    for field, value in movie_data.model_dump(exclude_unset=True).items():
        setattr(movie, field, value)

    try:
        await db.commit()
        await db.refresh(movie)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")

    return {"detail": "Movie updated successfully."}
