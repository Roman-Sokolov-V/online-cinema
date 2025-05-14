import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload, joinedload
from database import MovieModel, UserModel

Base_URL = "/api/v1/opinions/movies/favorite/"


async def get_movie(session):
    first_id_stmt = select(MovieModel.id).limit(1)
    first_id_result = await session.execute(first_id_stmt)
    first_id = first_id_result.scalar_one()

    stmt = select(MovieModel).where(MovieModel.id == first_id).options(
        joinedload(MovieModel.users_like))
    result = await session.execute(stmt)
    movie = result.scalars().first()
    return movie


async def get_user_and_header(session, data):
    header = {"Authorization": f"Bearer {data['access_token']}"}
    stmt = select(UserModel).where(
        UserModel.id == data["user"].id).options(
        joinedload(UserModel.favorite_movies))
    result = await session.execute(stmt)
    user = result.scalars().first()
    return user, header


@pytest.mark.asyncio
async def test_add_movie_to_favorite_successfully(client, db_session,
                                                  seed_database,
                                                  create_activate_login_user):
    user_data = await create_activate_login_user(group_name="user")
    user, header = await get_user_and_header(session=db_session,
                                             data=user_data)
    movie = await get_movie(session=db_session)

    assert movie is not None, "Should be movie in db"
    response = await client.post(Base_URL + f"{movie.id}/", headers=header)

    assert response.status_code == 201, "Expected 201 Created"
    await db_session.refresh(movie)
    assert user in movie.users_like, "Movie should be in users list of favorites"
    expected_response = "Movie successfully added to favorite list."
    assert expected_response == response.json()["detail"]


@pytest.mark.asyncio
async def test_add_not_existing_movie(client, db_session,
                                      create_activate_login_user):
    user_data = await create_activate_login_user(group_name="user")
    user, header = await get_user_and_header(session=db_session,
                                             data=user_data)
    movie_id = 1
    stmt = select(MovieModel).where(MovieModel.id == movie_id)
    result = await db_session.execute(stmt)
    movie = result.scalars().first()

    assert movie is None, "Should not be movie in db"
    response = await client.post(Base_URL + f"{movie_id}/", headers=header)

    assert response.status_code == 404, "Expected 404 code, movie not found."
    expected_response = "Movie with the given ID was not found."
    assert expected_response == response.json()["detail"]
    db_session.refresh(user)
    await db_session.commit()
    assert user.favorite_movies == [], "Should not be favorite movies in db"


@pytest.mark.asyncio
async def test_add_movie_that_already_in_favorite(client, db_session,
                                                  seed_database,
                                                  create_activate_login_user):
    user_data = await create_activate_login_user(group_name="user")
    user, header = await get_user_and_header(session=db_session,
                                             data=user_data)
    movie = await get_movie(session=db_session)
    assert movie is not None, "Should be movie in db"
    user.favorite_movies.append(movie)
    await db_session.commit()
    await db_session.refresh(movie)
    assert movie in user.favorite_movies, "Movie should be in favorite list"

    response = await client.post(Base_URL + f"{movie.id}/", headers=header)
    assert response.status_code == 400, "Expected 400"
    expected_response = "Movie already in favorite list."
    assert expected_response == response.json()["detail"]


@pytest.mark.asyncio
async def test_remove_movie_from_favorite_success(client, db_session,
                                                  seed_database,
                                                  create_activate_login_user):
    user_data = await create_activate_login_user(group_name="user")
    user, header = await get_user_and_header(session=db_session,
                                             data=user_data)
    movie = await get_movie(session=db_session)
    assert movie is not None, "Should be movie in db"
    response = await client.post(Base_URL + f"{movie.id}/", headers=header)
    assert response.status_code == 201, "Expected 201 Created"
    await db_session.refresh(movie)
    assert user in movie.users_like, "Movie should be in users list of favorites"

    response = await client.delete(Base_URL + f"{movie.id}/", headers=header)
    assert response.status_code == 200, "Expected 200"
    expected_response = "Movie successfully removed from favorite list."
    assert expected_response == response.json()["detail"]
    db_session.refresh(movie)
    await db_session.commit()
    assert movie not in user.favorite_movies, "Should not be movie in users list of favorites"


@pytest.mark.asyncio
async def test_remove_movie_from_favorite_list_that_not_in_list(
        client,
        db_session,
        seed_database,
        create_activate_login_user
):
    user_data = await create_activate_login_user(group_name="user")
    user, header = await get_user_and_header(session=db_session,
                                             data=user_data)
    movie = await get_movie(session=db_session)

    response = await client.delete(Base_URL + f"{movie.id}/", headers=header)
    assert response.status_code == 400, "Expected 400"
    expected_response = "Movie not found in favorite list."
    assert expected_response == response.json()["detail"]


async def get_user_header_favorite_movies(session, user_data):
    user, header = await get_user_and_header(session=session, data=user_data)

    stmt = select(MovieModel).options(
        selectinload(MovieModel.genres),
        selectinload(MovieModel.stars),
        selectinload(MovieModel.directors),
    )
    result = await session.execute(stmt)
    movies = result.scalars().all()
    user.favorite_movies.extend(movies)
    await session.commit()
    return user, header, movies


@pytest.mark.asyncio
async def test_get_favorites_with_custom_parameters(client, db_session,
                                                    seed_database,
                                                    create_activate_login_user):
    user_data = await create_activate_login_user(group_name="user")
    user, header, movies = await get_user_header_favorite_movies(
        session=db_session, user_data=user_data)

    response = await client.get(Base_URL, headers=header)
    assert response.status_code == 200, "Expected 200"
    movie_id_list = [movie.id for movie in movies]
    movie_id_list.sort()
    expected_movie_id = movie_id_list[:10]
    actual_movie_id = [movie["id"] for movie in response.json()["movies"]]
    actual_movie_id.sort()
    assert expected_movie_id == actual_movie_id


@pytest.mark.asyncio
async def test_get_favorites_with_filters(client, db_session, seed_database,
                                          create_activate_login_user):
    user_data = await create_activate_login_user(group_name="user")
    user, header, movies = await get_user_header_favorite_movies(
        session=db_session, user_data=user_data)
    genres = list(set([movie.genres[0].name for movie in movies]))[:2]
    actors = list(set([movie.stars[0].name for movie in movies]))[:2]
    directors = list(set([movie.directors[0].name for movie in movies]))[:2]
    year_param = movies[0].year
    min_rating_param = movies[0].imdb

    params_m2m ={
        "genres": ["|".join(genres), ",".join(genres), genres[0]],
        "stars": ["|".join(actors), ",".join(actors), actors[0]],
        "directors": ["|".join(directors), ",".join(directors), directors[0]],
    }
    for arg, params in params_m2m.items():
        for i, param in enumerate(params):
            if param is None:
                continue
            response = await client.get(
                Base_URL + f"?{arg}={param}", headers=header
            )
            assert response.status_code == 200, f"Expected 200, for ?{arg}={param}"
            expected_movie_id_list = []
            for movie in movies:
                arg_names = [arg.name for arg in getattr(movie, arg)]
                if i == 0:
                    param_1, param_2 = param.split("|")
                    if (param_1 in arg_names) or (param_2 in arg_names):
                        expected_movie_id_list.append(movie.id)
                elif i == 1:
                    param_1, param_2 = param.split(",")
                    if (param_1 in arg_names) and (param_2 in arg_names):
                        expected_movie_id_list.append(movie.id)
                else:
                    if param in arg_names:
                        expected_movie_id_list.append(movie.id)
            response_movie_id_list = [
                movie["id"] for movie in response.json()["movies"]
            ]
            assert set(expected_movie_id_list[:10]) == set(response_movie_id_list), f"expected movie_id sets and actual movie_id sets, should be equal for ?{arg}={param} filter"

    response = await client.get(
        Base_URL + f"?year={year_param}", headers=header
    )
    assert response.status_code == 200, "Expected 200"
    expected_movie_id_list = []
    for movie in movies:
        if year_param == movie.year:
            expected_movie_id_list.append(movie.id)

    response_movie_id_list = [
        movie["id"] for movie in response.json()["movies"]
    ]
    assert set(expected_movie_id_list[:10]) == set(response_movie_id_list)

    response = await client.get(
        Base_URL + f"?min_rating={min_rating_param}", headers=header
    )
    assert response.status_code == 200, "Expected 200"
    expected_movie_id_list = []
    for movie in movies:
        if min_rating_param <= movie.imdb:
            expected_movie_id_list.append(movie.id)

    response_movie_id_list = [
        movie["id"] for movie in response.json()["movies"]
    ]
    assert set(expected_movie_id_list[:10]) == set(response_movie_id_list)


@pytest.mark.asyncio
async def test_get_favorites_with_filters_sort_params(
        client,
        db_session,
        seed_database,
        create_activate_login_user
):
    user_data = await create_activate_login_user(group_name="user")
    user, header, movies = await get_user_header_favorite_movies(
        session=db_session,
        user_data=user_data
    )
    asc_params = {"price": "l-price", "year": "older"}
    desc_params = {"price": "h-price", "year": "newer", "imdb": "rating"}
    all_params = [asc_params, desc_params]
    for params in all_params:
        for arg_name, param in params.items():
            response = await client.get(
                Base_URL + f"?sort_params={param}", headers=header
            )
            assert response.status_code == 200, "Expected 200"
            expected_movie_id_list = [
                movie.id for movie
                in sorted(
                    movies,
                    key=lambda movie: getattr(movie, arg_name),
                    reverse=(params == desc_params)
                )[:10]
            ]
            response_movie_id_list = [
                movie["id"] for movie in response.json()["movies"]
            ]
            assert expected_movie_id_list == response_movie_id_list
