import random

import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload, selectinload

from database import MovieModel, CertificationModel
from database import (
    GenreModel,
    StarModel,
    DirectorModel,

)


@pytest.mark.asyncio
async def test_get_movies_empty_database(client):
    """
    Test that the `/movies/` endpoint returns a 404 error when the database is empty.
    """
    response = await client.get("/api/v1/theater/movies/")
    assert response.status_code == 404, f"Expected 404, got {response.status_code}"

    expected_detail = {"detail": "No movies found."}
    assert response.json() == expected_detail, f"Expected {expected_detail}, got {response.json()}"


@pytest.mark.asyncio
async def test_get_movies_default_parameters(client, seed_database):
    """
    Test the `/movies/` endpoint with default pagination parameters.
    """
    response = await client.get("/api/v1/theater/movies/")
    assert response.status_code == 200, "Expected status code 200, but got a different value"

    response_data = response.json()

    assert len(response_data[
                   "movies"]) == 10, "Expected 10 movies in the response, but got a different count"

    assert response_data[
               "total_pages"] > 0, "Expected total_pages > 0, but got a non-positive value"
    assert response_data[
               "total_items"] > 0, "Expected total_items > 0, but got a non-positive value"

    assert response_data[
               "prev_page"] is None, "Expected prev_page to be None on the first page, but got a value"

    if response_data["total_pages"] > 1:
        assert response_data["next_page"] is not None, (
            "Expected next_page to be present when total_pages > 1, but got None"
        )


@pytest.mark.asyncio
async def test_get_movies_with_custom_parameters(client, seed_database):
    """
    Test the `/movies/` endpoint with custom pagination parameters.
    """
    page = 2
    per_page = 5

    response = await client.get(
        f"/api/v1/theater/movies/?page={page}&per_page={per_page}")

    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()

    assert len(response_data["movies"]) == per_page, (
        f"Expected {per_page} movies in the response, but got {len(response_data['movies'])}"
    )

    assert response_data[
               "total_pages"] > 0, "Expected total_pages > 0, but got a non-positive value"
    assert response_data[
               "total_items"] > 0, "Expected total_items > 0, but got a non-positive value"

    if page > 1:
        assert response_data[
                   "prev_page"] == f"/theater/movies/?page={page - 1}&per_page={per_page}", (
            f"Expected prev_page to be '/theater/movies/?page={page - 1}&per_page={per_page}', "
            f"but got {response_data['prev_page']}"
        )

    if page < response_data["total_pages"]:
        assert response_data[
                   "next_page"] == f"/theater/movies/?page={page + 1}&per_page={per_page}", (
            f"Expected next_page to be '/theater/movies/?page={page + 1}&per_page={per_page}', "
            f"but got {response_data['next_page']}"
        )
    else:
        assert response_data[
                   "next_page"] is None, "Expected next_page to be None on the last page, but got a value"


@pytest.mark.asyncio
@pytest.mark.parametrize("page, per_page, expected_detail", [
    (0, 10, "Input should be greater than or equal to 1"),
    (1, 0, "Input should be greater than or equal to 1"),
    (0, 0, "Input should be greater than or equal to 1"),
])
async def test_invalid_page_and_per_page(client, page, per_page,
                                         expected_detail):
    """
    Test the `/movies/` endpoint with invalid `page` and `per_page` parameters.
    """
    response = await client.get(
        f"/api/v1/theater/movies/?page={page}&per_page={per_page}")

    assert response.status_code == 422, (
        f"Expected status code 422 for invalid parameters, but got {response.status_code}"
    )

    response_data = response.json()

    assert "detail" in response_data, "Expected 'detail' in the response, but it was missing"

    assert any(expected_detail in error["msg"] for error in
               response_data["detail"]), (
        f"Expected error message '{expected_detail}' in the response details, but got {response_data['detail']}"
    )


@pytest.mark.asyncio
async def test_per_page_maximum_allowed_value(client, seed_database):
    """
    Test the `/movies/` endpoint with the maximum allowed `per_page` value.
    """
    response = await client.get("/api/v1/theater/movies/?page=1&per_page=20")

    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()

    assert "movies" in response_data, "Response missing 'movies' field."
    assert len(response_data["movies"]) <= 20, (
        f"Expected at most 20 movies, but got {len(response_data['movies'])}"
    )


@pytest.mark.asyncio
async def test_page_exceeds_maximum(client, db_session, seed_database):
    """
    Test the `/movies/` endpoint with a page number that exceeds the maximum.
    """
    per_page = 10

    count_stmt = select(func.count(MovieModel.id))
    result = await db_session.execute(count_stmt)
    total_movies = result.scalar_one()

    max_page = (total_movies + per_page - 1) // per_page

    response = await client.get(
        f"/api/v1/theater/movies/?page={max_page + 1}&per_page={per_page}")

    assert response.status_code == 404, f"Expected status code 404, but got {response.status_code}"
    response_data = response.json()

    assert "detail" in response_data, "Response missing 'detail' field."


@pytest.mark.asyncio
async def test_movies_sorted_by_id_desc(client, db_session, seed_database):
    """
    Test that movies are returned sorted by `id` in descending order
    and match the expected data from the database.
    """
    response = await client.get("/api/v1/theater/movies/?page=1&per_page=10")

    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()

    stmt = select(MovieModel).order_by(MovieModel.id.desc()).limit(10)
    result = await db_session.execute(stmt)
    expected_movies = result.scalars().all()

    expected_movie_ids = [movie.id for movie in expected_movies]
    returned_movie_ids = [movie["id"] for movie in response_data["movies"]]

    assert returned_movie_ids == expected_movie_ids, (
        f"Movies are not sorted by `id` in descending order. "
        f"Expected: {expected_movie_ids}, but got: {returned_movie_ids}"
    )


@pytest.mark.asyncio
async def test_movies_sorted_by_price_desc(client, db_session, seed_database):
    """
    Test that movies are returned sorted by `price` in descending order
    and match the expected data from the database.
    """
    response = await client.get(
        "/api/v1/theater/movies/?page=1&per_page=10&sort_params=h-price")

    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()

    stmt = select(MovieModel).order_by(MovieModel.price.desc()).limit(10)
    result = await db_session.execute(stmt)
    expected_movies = result.scalars().all()

    expected_movie_ids = [movie.id for movie in expected_movies]
    returned_movie_ids = [movie["id"] for movie in response_data["movies"]]

    assert returned_movie_ids == expected_movie_ids, (
        f"Movies are not sorted by `price` in descending order. "
        f"Expected: {expected_movie_ids}, but got: {returned_movie_ids}"
    )


@pytest.mark.asyncio
async def test_movies_sorted_by_price_asc(client, db_session, seed_database):
    """
    Test that movies are returned sorted by `price` in descending order
    and match the expected data from the database.
    """
    response = await client.get(
        "/api/v1/theater/movies/?page=1&per_page=10&sort_params=l-price")

    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()

    stmt = select(MovieModel).order_by(MovieModel.price.asc()).limit(10)
    result = await db_session.execute(stmt)
    expected_movies = result.scalars().all()

    expected_movie_ids = [movie.id for movie in expected_movies]
    returned_movie_ids = [movie["id"] for movie in response_data["movies"]]

    assert returned_movie_ids == expected_movie_ids, (
        f"Movies are not sorted by `price` in ascending order. "
        f"Expected: {expected_movie_ids}, but got: {returned_movie_ids}"
    )


@pytest.mark.asyncio
async def test_movies_sorted_by_year_desc(client, db_session, seed_database):
    """
    Test that movies are returned sorted by `year` in descending order
    and match the expected data from the database.
    """
    response = await client.get(
        "/api/v1/theater/movies/?page=1&per_page=10&sort_params=newer")

    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()

    stmt = select(MovieModel).order_by(MovieModel.year.desc()).limit(10)
    result = await db_session.execute(stmt)
    expected_movies = result.scalars().all()

    expected_movie_ids = [movie.id for movie in expected_movies]
    returned_movie_ids = [movie["id"] for movie in response_data["movies"]]

    assert returned_movie_ids == expected_movie_ids, (
        f"Movies are not sorted by `year` in descending order. "
        f"Expected: {expected_movie_ids}, but got: {returned_movie_ids}"
    )


@pytest.mark.asyncio
async def test_movies_sorted_by_year_asc(client, db_session, seed_database):
    """
    Test that movies are returned sorted by `year` in descending order
    and match the expected data from the database.
    """
    response = await client.get(
        "/api/v1/theater/movies/?page=1&per_page=10&sort_params=older")

    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()

    stmt = select(MovieModel).order_by(MovieModel.year.asc()).limit(10)
    result = await db_session.execute(stmt)
    expected_movies = result.scalars().all()

    expected_movie_ids = [movie.id for movie in expected_movies]
    returned_movie_ids = [movie["id"] for movie in response_data["movies"]]

    assert returned_movie_ids == expected_movie_ids, (
        f"Movies are not sorted by `year` in ascending order. "
        f"Expected: {expected_movie_ids}, but got: {returned_movie_ids}"
    )


@pytest.mark.asyncio
async def test_movies_sorted_by_imdb_desc(client, db_session, seed_database):
    """
    Test that movies are returned sorted by `imdb` in descending order
    and match the expected data from the database.
    """
    response = await client.get(
        "/api/v1/theater/movies/?page=1&per_page=10&sort_params=rating")

    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()

    stmt = select(MovieModel).order_by(MovieModel.imdb.desc()).limit(10)
    result = await db_session.execute(stmt)
    expected_movies = result.scalars().all()

    expected_movie_ids = [movie.id for movie in expected_movies]
    returned_movie_ids = [movie["id"] for movie in response_data["movies"]]

    assert returned_movie_ids == expected_movie_ids, (
        f"Movies are not sorted by `imdb` in descending order. "
        f"Expected: {expected_movie_ids}, but got: {returned_movie_ids}"
    )


@pytest.mark.asyncio
async def test_movie_list_with_pagination(client, db_session, seed_database):
    """
    Test the `/movies/` endpoint with pagination parameters.

    Verifies the following:
    - The response status code is 200.
    - Total items and total pages match the expected values from the database.
    - The movies returned match the expected movies for the given page and per_page.
    - The `prev_page` and `next_page` links are correct.
    """
    page = 2
    per_page = 5
    offset = (page - 1) * per_page

    response = await client.get(
        f"/api/v1/theater/movies/?page={page}&per_page={per_page}")
    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()

    count_stmt = select(func.count(MovieModel.id))
    count_result = await db_session.execute(count_stmt)
    total_items = count_result.scalar_one()

    total_pages = (total_items + per_page - 1) // per_page

    assert response_data["total_items"] == total_items, "Total items mismatch."
    assert response_data["total_pages"] == total_pages, "Total pages mismatch."

    stmt = (
        select(MovieModel)
        .order_by(MovieModel.id.desc())
        .offset(offset)
        .limit(per_page)
    )
    result = await db_session.execute(stmt)
    expected_movies = result.scalars().all()

    expected_movie_ids = [movie.id for movie in expected_movies]
    returned_movie_ids = [movie["id"] for movie in response_data["movies"]]

    assert expected_movie_ids == returned_movie_ids, "Movies on the page mismatch."

    expected_prev_page = f"/theater/movies/?page={page - 1}&per_page={per_page}" if page > 1 else None
    expected_next_page = f"/theater/movies/?page={page + 1}&per_page={per_page}" if page < total_pages else None

    assert response_data[
               "prev_page"] == expected_prev_page, "Previous page link mismatch."
    assert response_data[
               "next_page"] == expected_next_page, "Next page link mismatch."


@pytest.mark.asyncio
async def test_movie_list_with_filter_by_genres(client, db_session,
                                                seed_database):
    """
    Test the `/movies/` endpoint with filter by genres.

    Verifies the following:
    - The response status code is 200.
    - All items should satisfy the filtering parameters
    """

    response = await client.get("/api/v1/theater/movies/?genres=action")
    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"
    response_data = response.json()
    for movie in response_data["movies"]:
        assert "action" in [genre["name"] for genre in movie[
            "genres"]], "in every movie should be genre - action"

    response = await client.get("/api/v1/theater/movies/?genres=action|horror")
    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"
    response_data = response.json()
    for movie in response_data["movies"]:
        genres = [genre["name"] for genre in movie["genres"]]
        assert (
                ("action" in genres) or ("horror" in genres)
        ), "in every movie should be genre - action or horror"
    response = await client.get("/api/v1/theater/movies/?genres=action,horror")
    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"
    response_data = response.json()
    for movie in response_data["movies"]:
        genres = [genre["name"] for genre in movie["genres"]]
        assert (
                ("action" in genres) and ("horror" in genres)
        ), "in every movie should be genre - action and horror"


@pytest.mark.asyncio
async def test_movie_list_with_filter_by_stars(
        client, db_session, seed_database
):
    """
    Test the `/movies/` endpoint with filter by stars.

    Verifies the following:
    - The response status code is 200.
    - All items should satisfy the filtering parameters
    """
    star_1 = "Ben Stiller"
    star_2 = "Gwyneth Paltrow"
    response = await client.get(f"/api/v1/theater/movies/?stars={star_1}")
    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"
    response_data = response.json()

    for movie in response_data["movies"]:
        stars = {star["name"] for star in movie["stars"]}
        assert star_1 in stars, f"in every movie should by star - {star_1}"

    response = await client.get(
        f"/api/v1/theater/movies/?stars={star_1}|{star_2}")
    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"
    response_data = response.json()
    for movie in response_data["movies"]:
        stars = {star["name"] for star in movie["stars"]}
        assert (
                (star_1 in stars) or (star_2 in stars)
        ), "in every movie should be stars - {star_1} or {star_2}"

    response = await client.get(
        f"/api/v1/theater/movies/?stars={star_1},{star_2}")
    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"
    response_data = response.json()
    for movie in response_data["movies"]:
        stars = {star["name"] for star in movie["stars"]}
        assert (
            stars.issuperset({star_1, star_2}),
            f"in every movie should be stars - {star_1} and {star_2}"
        )


@pytest.mark.asyncio
async def test_movie_list_with_filter_by_directors(
        client, db_session, seed_database
):
    """
    Test the `/movies/` endpoint with filter by directors.

    Verifies the following:
    - The response status code is 200.
    - All items should satisfy the filtering parameters
    """
    director_1 = "George Lucas"
    director_2 = "Peter Weir"
    response = await client.get(
        f"/api/v1/theater/movies/?directors={director_1}")
    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"
    response_data = response.json()

    for movie in response_data["movies"]:
        directors = {director["name"] for director in movie["directors"]}
        assert director_1 in directors, f"in every movie should by star - {director_1}"

    response = await client.get(
        f"/api/v1/theater/movies/?directors={director_1}|{director_2}")
    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"
    response_data = response.json()
    for movie in response_data["movies"]:
        directors = {director["name"] for director in movie["directors"]}
        assert (
                (director_1 in directors) or (director_2 in directors)
        ), "in every movie should be directors - {director_1} or {director_2}"

    response = await client.get(
        f"/api/v1/theater/movies/?directors={director_1},{director_2}")
    assert response.status_code == 404, f"Expected status code 404, if no movies were exists both directors, but got {response.status_code}"

    stmt = select(DirectorModel).where(DirectorModel.name == director_2)
    result = await db_session.execute(stmt)
    second_director = result.scalar_one()

    stmt = (
        select(MovieModel)
        .join(MovieModel.directors)
        .where(DirectorModel.name == director_1)
        .options(selectinload(MovieModel.directors))
    )
    result = await db_session.execute(stmt)
    movie = result.scalars().first()
    movie.directors.append(second_director)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/theater/movies/?directors={director_1},{director_2}")
    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"
    response_data = response.json()
    assert len(response_data["movies"]) == 1
    response_movie = response_data["movies"][0]
    directors = {director["name"] for director in response_movie["directors"]}
    assert (
        directors.issuperset({director_1, director_2}),
        f"in every movie should be directors - {director_1} and {director_2}"
    )


@pytest.mark.asyncio
async def test_movies_fields_match_schema(client, db_session, seed_database):
    """
    Test that each movie in the response matches the fields defined in `MovieListItemSchema`.
    """
    response = await client.get("/api/v1/theater/movies/?page=1&per_page=10")

    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()

    assert "movies" in response_data, "Response missing 'movies' field."

    expected_fields = [c.name for c in MovieModel.__table__.columns] + [
        "genres", "directors", "stars"]

    for movie in response_data["movies"]:
        assert set(movie.keys()) == set(expected_fields), (
            f"Movie fields do not match schema. "
            f"Expected: {expected_fields}, but got: {set(movie.keys())}"
        )


@pytest.mark.asyncio
async def test_get_movie_by_id_not_found(client):
    """
    Test that the `/movies/{movie_id}` endpoint returns a 404 error
    when a movie with the given ID does not exist.
    """
    movie_id = 1

    response = await client.get(f"/api/v1/theater/movies/{movie_id}/")
    assert response.status_code == 404, f"Expected status code 404, but got {response.status_code}"

    response_data = response.json()
    assert response_data == {
        "detail": "Movie with the given ID was not found."}, (
        f"Expected error message not found. Got: {response_data}"
    )


@pytest.mark.asyncio
async def test_get_movie_by_id_valid(client, db_session, seed_database):
    """
    Test that the `/movies/{movie_id}` endpoint returns the correct movie details
    when a valid movie ID is provided.

    Verifies the following:
    - The movie exists in the database.
    - The response status code is 200.
    - The movie's `id` and `name` in the response match the expected values from the database.
    """
    stmt_min = select(MovieModel.id).order_by(MovieModel.id.asc()).limit(1)
    result_min = await db_session.execute(stmt_min)
    min_id = result_min.scalars().first()

    stmt_max = select(MovieModel.id).order_by(MovieModel.id.desc()).limit(1)
    result_max = await db_session.execute(stmt_max)
    max_id = result_max.scalars().first()

    random_id = random.randint(min_id, max_id)

    stmt_movie = select(MovieModel).where(MovieModel.id == random_id)
    result_movie = await db_session.execute(stmt_movie)
    expected_movie = result_movie.scalars().first()
    assert expected_movie is not None, "Movie not found in database."

    response = await client.get(f"/api/v1/theater/movies/{random_id}/")
    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()

    assert response_data[
               "id"] == expected_movie.id, "Returned ID does not match the requested ID."
    assert response_data[
               "name"] == expected_movie.name, "Returned name does not match the expected name."


@pytest.mark.asyncio
async def test_get_movie_by_id_fields_match_database(client, db_session,
                                                     seed_database):
    """
    Test that the `/movies/{movie_id}` endpoint returns all fields matching the database data.
    """
    stmt = (
        select(MovieModel)
        .options(
            joinedload(MovieModel.genres),
            joinedload(MovieModel.stars),
            joinedload(MovieModel.directors),
        )
        .limit(1)
    )
    result = await db_session.execute(stmt)
    random_movie = result.scalars().first()
    assert random_movie is not None, "No movies found in the database."

    response = await client.get(f"/api/v1/theater/movies/{random_movie.id}/")
    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()

    assert response_data["id"] == random_movie.id, "ID does not match."
    assert response_data["name"] == random_movie.name, "Name does not match."
    assert response_data[
               "year"] == random_movie.year, "Year does not match."
    assert response_data[
               "time"] == random_movie.time, "Time does not match."
    assert response_data[
               "imdb"] == random_movie.imdb, "Imdb does not match."
    assert response_data[
               "votes"] == random_movie.votes, "Votes does not match."
    assert response_data["meta_score"] == random_movie.meta_score, "Budget does not match."
    assert response_data[
               "gross"] == random_movie.gross, "Gross does not match."

    assert response_data["description"] == random_movie.description, "Description does not match."
    assert response_data["price"] == str(random_movie.price), "Price code does not match."

    actual_genres = sorted(response_data["genres"], key=lambda x: x["id"])
    expected_genres = sorted(
        [{"id": genre.id, "name": genre.name} for genre in
         random_movie.genres],
        key=lambda x: x["id"]
    )
    assert actual_genres == expected_genres, "Genres do not match."

    actual_stars = sorted(response_data["stars"], key=lambda x: x["id"])
    expected_stars = sorted(
        [{"id": star.id, "name": star.name} for star in
         random_movie.stars],
        key=lambda x: x["id"]
    )
    assert actual_stars == expected_stars, "Stars do not match."

    actual_directors = sorted(response_data["directors"],
                              key=lambda x: x["id"])
    expected_directors = sorted(
        [{"id": director.id, "name": director.name} for director in
         random_movie.directors],
        key=lambda x: x["id"]
    )
    assert actual_directors == expected_directors, "Directors do not match."

@pytest.mark.asyncio
async def test_create_movie_and_related_models(client, db_session, create_activate_login_user):
    """
    Test that a new movie is created successfully and related models
    (genres, stars, directors, certification) are created if they do not exist.
    """
    moderator_data = await create_activate_login_user(group_name="moderator")
    moderator_access_token = moderator_data["access_token"]
    headers = {"Authorization": f"Bearer {moderator_access_token}"}
    movie_data = {
        "name": "New Movie",
        "year": 2020,
        "time": 102,
        "imdb": 7.8,
        "votes": 2365,
        "meta_score": 5.8,
        "gross": 1000000.00,
        "description": "An amazing movie.",
        "price": 8.99,
        "certification_name": "PG-13",
        "genres": ["action", "crime"],
        "stars": ["John Doe", "Jane Doe"],
        "directors": ["John Smith", "Jane Smith"],
    }

    response = await client.post("/api/v1/theater/movies/", json=movie_data, headers=headers)
    assert response.status_code == 201, f"Expected status code 201, but got {response.status_code}"

    response_data = response.json()
    assert response_data["name"] == movie_data[
        "name"], "Movie name does not match."
    assert response_data["year"] == movie_data[
        "year"], "Year date does not match."
    assert response_data["time"] == movie_data[
        "time"], "Time does not match."
    assert response_data["imdb"] == movie_data[
        "imdb"], "Imdb overview does not match."
    assert response_data["votes"] == movie_data[
        "votes"], "Votes overview does not match."
    assert response_data["meta_score"] == movie_data[
        "meta_score"], "Meta_score overview does not match."
    assert response_data["gross"] == movie_data[
        "gross"], "Gross overview does not match."
    assert response_data["description"] == movie_data[
        "description"], "Description overview does not match."
    assert response_data["price"] == str(movie_data[
        "price"]), "Price overview does not match."

    for genre_name in movie_data["genres"]:
        stmt = select(GenreModel).where(GenreModel.name == genre_name)
        result = await db_session.execute(stmt)
        genre = result.scalars().first()
        assert genre is not None, f"Genre '{genre_name}' was not created."

    for star_name in movie_data["stars"]:
        stmt = select(StarModel).where(StarModel.name == star_name)
        result = await db_session.execute(stmt)
        star = result.scalars().first()
        assert star is not None, f"Star '{star_name}' was not created."

    for director_name in movie_data["directors"]:
        stmt = select(DirectorModel).where(DirectorModel.name == director_name)
        result = await db_session.execute(stmt)
        director = result.scalars().first()
        assert director is not None, f"Director '{director_name}' was not created."

    stmt = select(CertificationModel).where(
        CertificationModel.name == movie_data["certification_name"])
    result = await db_session.execute(stmt)
    country = result.scalars().first()
    assert country is not None, f"Certification '{movie_data['certification_name']}' was not created."


@pytest.mark.asyncio
async def test_create_movie_duplicate_error(client, db_session, create_activate_login_user):
    """
    Test that trying to create a movie with the same name and date as an existing movie
    results in a 409 conflict error.
    """

    moderator_data = await create_activate_login_user(group_name="moderator")
    moderator_access_token = moderator_data["access_token"]
    headers = {"Authorization": f"Bearer {moderator_access_token}"}
    name = "New Movie"
    year = 2020
    time = 102
    movie_data = {
        "name": name,
        "year": year,
        "time": time,
        "imdb": 7.8,
        "votes": 2365,
        "meta_score": 5.8,
        "gross": 1000000.00,
        "description": "An amazing movie.",
        "price": 8.99,
        "certification_name": "PG-13",
        "genres": ["action", "crime"],
        "stars": ["John Doe", "Jane Doe"],
        "directors": ["John Smith", "Jane Smith"],
    }
    response = await client.post(
        "/api/v1/theater/movies/", json=movie_data, headers=headers
    )
    assert response.status_code == 201, f"Expected status code 201, but got {response.status_code}"

    new_movie_data = {
        "name": name,
        "year": year,
        "time": time,
        "imdb": 8,
        "votes": 3000,
        "meta_score": 6,
        "gross": 1003300.00,
        "description": "Bad movie.",
        "price": 3,
        "certification_name": "PG",
        "genres": [],
        "stars": [],
        "directors": [],
    }

    response = await client.post("/api/v1/theater/movies/", json=new_movie_data, headers=headers)
    assert response.status_code == 409, f"Expected status code 409, but got {response.status_code}"

    response_data = response.json()
    expected_detail = (
        f"A movie with the name '{new_movie_data['name']}', release year '{new_movie_data['year']}' and duration time '{new_movie_data['time']}' already exists."
    )
    assert response_data["detail"] == expected_detail, (
        f"Expected detail message: {expected_detail}, but got: {response_data['detail']}"
    )

@pytest.mark.asyncio
async def test_permissions_to_create_movie(client, db_session, create_activate_login_user):
    """
    Test that trying to create a movie by users from  group: user, moderator, admin.
    User from user-group do not permissions to create movie
    """

    user_data = await create_activate_login_user(
        group_name="user")
    user_access_token = user_data["access_token"]
    user_headers = {"Authorization": f"Bearer {user_access_token}"}

    moderator_data = await create_activate_login_user(
        group_name="moderator")
    moderator_access_token = moderator_data["access_token"]
    moderator_headers = {"Authorization": f"Bearer {moderator_access_token}"}

    admin_data = await create_activate_login_user(
        group_name="admin")
    admin_access_token = admin_data["access_token"]
    admin_headers = {
        "Authorization": f"Bearer {admin_access_token}"}

    movie_data = {
        "name": "New Movie",
        "year": 2020,
        "time": 102,
        "imdb": 7.8,
        "votes": 2365,
        "meta_score": 5.8,
        "gross": 1000000.00,
        "description": "An amazing movie.",
        "price": 8.99,
        "certification_name": "PG-13",
        "genres": ["action", "crime"],
        "stars": ["John Doe", "Jane Doe"],
        "directors": ["John Smith", "Jane Smith"],
    }
    response = await client.post(
        "/api/v1/theater/movies/", json=movie_data, headers=user_headers
    )
    assert response.status_code == 403, f"Expected status code 403, but got {response.status_code}"
    response = await client.post(
        "/api/v1/theater/movies/", json=movie_data, headers=moderator_headers
    )
    assert response.status_code == 201, f"Expected status code 201, but got {response.status_code}"
    # change movie_data["name"] no avoid 409 exception (try creating exists movie)
    movie_data["name"] = "Old York"

    response = await client.post(
        "/api/v1/theater/movies/", json=movie_data, headers=admin_headers
    )
    assert response.status_code == 201, f"Expected status code 201, but got {response.status_code}"


###########################################################################
@pytest.mark.asyncio
async def test_delete_movie_by_all_user_groups(client, db_session, seed_database, create_activate_login_user):
    """
    Test that trying to delete a movie by users from  group: user, moderator, admin.
    User from user-group do not permissions to delete movie
    """
    user_data = await create_activate_login_user(
        group_name="user")
    user_access_token = user_data["access_token"]
    user_headers = {"Authorization": f"Bearer {user_access_token}"}

    moderator_data = await create_activate_login_user(
        group_name="moderator")
    moderator_access_token = moderator_data["access_token"]
    moderator_headers = {"Authorization": f"Bearer {moderator_access_token}"}

    admin_data = await create_activate_login_user(
        group_name="admin")
    admin_access_token = admin_data["access_token"]
    admin_headers = {
        "Authorization": f"Bearer {admin_access_token}"}

    stmt = select(MovieModel).limit(3)
    result = await db_session.execute(stmt)
    movies = result.scalars().all()
    assert len(movies) == 3, "No 3 movies found in the database to delete."
    first_movie_id = movies[0].id
    second_movie_id = movies[1].id
    third_movie_id = movies[2].id
    response = await client.delete(
        f"/api/v1/theater/movies/{first_movie_id}/", headers=user_headers
    )
    assert response.status_code == 403, f"Expected status code 403, but got {response.status_code}"
    response = await client.delete(
        f"/api/v1/theater/movies/{second_movie_id}/", headers=moderator_headers
    )
    assert response.status_code == 204, f"Expected status code 204, but got {response.status_code}"
    response = await client.delete(
        f"/api/v1/theater/movies/{third_movie_id}/", headers=admin_headers
    )
    assert response.status_code == 204, f"Expected status code 204, but got {response.status_code}"
    movie_1_from_db = await db_session.scalar(
        select(MovieModel).where(MovieModel.id == first_movie_id))
    movie_2_from_db = await db_session.scalar(
        select(MovieModel).where(MovieModel.id == second_movie_id))
    movie_3_from_db = await db_session.scalar(
        select(MovieModel).where(MovieModel.id == third_movie_id)
    )

    assert movie_1_from_db is not None, (
        "User from user-group, do not has permissions to delete movie, "
        "movie should still be in database.")
    assert movie_2_from_db is None, "Movie should be deleted from database"
    assert movie_3_from_db is None, "Movie should be deleted from database"

@pytest.mark.asyncio
async def test_delete_movie_success(
        client, db_session, seed_database, create_activate_login_user
):
    """
    Test the `/movies/{movie_id}/` endpoint for successful movie deletion.
    """
    request_user_data = await create_activate_login_user("moderator")
    headers = {"Authorization": f"Bearer {request_user_data['access_token']}"}

    stmt = select(MovieModel).limit(1)
    result = await db_session.execute(stmt)
    movie = result.scalars().first()
    assert movie is not None, "No movies found in the database to delete."

    movie_id = movie.id

    response = await client.delete(f"/api/v1/theater/movies/{movie_id}/", headers=headers)
    assert response.status_code == 204, f"Expected status code 204, but got {response.status_code}"

    stmt_check = select(MovieModel).where(MovieModel.id == movie_id)
    result_check = await db_session.execute(stmt_check)
    deleted_movie = result_check.scalars().first()
    assert deleted_movie is None, f"Movie with ID {movie_id} was not deleted."
#########################################################################################

@pytest.mark.asyncio
async def test_delete_movie_not_found(client, create_activate_login_user):
    """
    Test the `/movies/{movie_id}/` endpoint with a non-existent movie ID.
    """
    moderator_data = await create_activate_login_user(
        group_name="moderator")
    moderator_access_token = moderator_data["access_token"]
    moderator_headers = {"Authorization": f"Bearer {moderator_access_token}"}

    non_existent_id = 99999

    response = await client.delete(
        f"/api/v1/theater/movies/{non_existent_id}/", headers=moderator_headers
    )
    assert response.status_code == 404, f"Expected status code 404, but got {response.status_code}"

    response_data = response.json()
    expected_detail = "Movie with the given ID was not found."
    assert response_data["detail"] == expected_detail, (
        f"Expected detail message: {expected_detail}, but got: {response_data['detail']}"
    )


# @pytest.mark.asyncio
# async def test_update_movie_success(client, db_session, seed_database):
#     """
#     Test the `/movies/{movie_id}/` endpoint for successfully updating a movie's details.
#     """
#     stmt = select(MovieModel).limit(1)
#     result = await db_session.execute(stmt)
#     movie = result.scalars().first()
#     assert movie is not None, "No movies found in the database to update."
#
#     movie_id = movie.id
#     update_data = {
#         "name": "Updated Movie Name",
#         "score": 95.0,
#     }
#
#     response = await client.patch(f"/api/v1/theater/movies/{movie_id}/",
#                                   json=update_data)
#     assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"
#
#     response_data = response.json()
#     assert response_data["detail"] == "Movie updated successfully.", (
#         f"Expected detail message: 'Movie updated successfully.', but got: {response_data['detail']}"
#     )
#
#     await db_session.rollback()
#
#     stmt_check = select(MovieModel).where(MovieModel.id == movie_id)
#     result_check = await db_session.execute(stmt_check)
#     updated_movie = result_check.scalars().first()
#
#     assert updated_movie.name == update_data[
#         "name"], "Movie name was not updated."
#     assert updated_movie.score == update_data[
#         "score"], "Movie score was not updated."
#
#
# @pytest.mark.asyncio
# async def test_update_movie_not_found(client):
#     """
#     Test the `/movies/{movie_id}/` endpoint with a non-existent movie ID.
#     """
#     non_existent_id = 99999
#     update_data = {
#         "name": "Non-existent Movie",
#         "score": 90.0
#     }
#
#     response = await client.patch(f"/api/v1/theater/movies/{non_existent_id}/",
#                                   json=update_data)
#     assert response.status_code == 404, f"Expected status code 404, but got {response.status_code}"
#
#     response_data = response.json()
#     expected_detail = "Movie with the given ID was not found."
#     assert response_data["detail"] == expected_detail, (
#         f"Expected detail message: {expected_detail}, but got: {response_data['detail']}"
#     )
