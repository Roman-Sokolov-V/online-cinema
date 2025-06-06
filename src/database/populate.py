import asyncio
import math
import random
from decimal import Decimal
from typing import List, Dict, Tuple

import pandas as pd
from sqlalchemy import insert, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from tqdm import tqdm

from config import get_settings
from database import (
    GenreModel,
    MoviesGenresModel,
    MovieModel, UserGroupModel, UserGroupEnum, CertificationModel, StarModel,
    MoviesStarsModel, MoviesDirectorsModel, DirectorModel, UserModel
)
from database import get_db_contextmanager

CHUNK_SIZE = 1000


class CSVDatabaseSeeder:
    """
    A class responsible for seeding the database from a CSV file using asynchronous SQLAlchemy.
    """

    def __init__(self, csv_file_path: str, db_session: AsyncSession) -> None:
        """
        Initialize the seeder with the path to the CSV file and an async database session.

        :param csv_file_path: The path to the CSV file containing movie data.
        :param db_session: An instance of AsyncSession for performing database operations.
        """
        self._csv_file_path = csv_file_path
        self._db_session = db_session

    async def is_db_populated(self) -> bool:
        """
        Check if the MovieModel table has at least one record.

        :return: True if there's already at least one movie in the database, otherwise False.
        """
        result = await self._db_session.execute(select(MovieModel).limit(1))
        first_movie = result.scalars().first()
        return first_movie is not None

    def _preprocess_csv(self) -> pd.DataFrame:
        """
        Load the CSV, remove duplicates, convert relevant columns to strings, and clean up data.
        Saves the cleaned CSV back to the same path, then returns the Pandas DataFrame.

        :return: A Pandas DataFrame containing cleaned movie data.
        """

        data = pd.read_csv(self._csv_file_path, usecols=lambda x: x != 'Unnamed: 15')
        data = data.dropna(axis=0)

        data = data.drop_duplicates(subset=['Title', 'Released_Year', "Runtime"], keep='first')

        data["Title"] = data["Title"].str.strip()

        data["Certificate"] = data["Certificate"].str.strip()

        if pd.api.types.is_object_dtype(data["Runtime"]):
            data["Runtime"] = data["Runtime"].str.strip().str.split().str[
                0].astype(int)

        data["Genre"] = (
            data["Genre"]
            .str.lower()
            .replace(r'\s+', '', regex=True)
            .apply(lambda x: ','.join(sorted(set(x.split(',')))) if x != 'Unknown' else x)
        )

        data["Overview"] = data["Overview"].str.strip()

        if pd.api.types.is_object_dtype(data["Meta_score"]):
            data["Meta_score"] = data["Meta_score"].str.strip().astype(float)

        data["Director"] = data["Director"].str.strip()
        data["Star1"] = data["Star1"].str.strip()
        data["Star2"] = data["Star2"].str.strip()
        data["Star3"] = data["Star3"].str.strip()
        data["Star4"] = data["Star4"].str.strip()

        if pd.api.types.is_object_dtype(data["No_of_Votes"]):
            data["No_of_Votes"] = data["No_of_Votes"].str.strip().astype(int)

        if pd.api.types.is_object_dtype(data["Gross"]):
            data["Gross"] = data["Gross"].str.replace(",", "").astype(float)

        print("Preprocessing CSV file...")
        data.to_csv(self._csv_file_path, index=False)
        print(f"CSV file saved to {self._csv_file_path}")
        return data

    async def _seed_user_groups(self) -> None:
        """
        Seed the UserGroupModel table with default user groups if none exist.

        This method checks whether any user groups are already present in the database.
        If no records are found, it inserts all groups defined in the UserGroupEnum.
        After insertion, the changes are flushed to the current transaction.
        """
        count_stmt = select(func.count(UserGroupModel.id))
        result = await self._db_session.execute(count_stmt)
        existing_groups = result.scalar()

        if existing_groups == 0:
            groups = [{"name": group.value} for group in UserGroupEnum]
            await self._db_session.execute(
                insert(UserGroupModel).values(groups))
            await self._db_session.flush()

            print("User groups seeded successfully.")

    async def _get_or_create_bulk(
            self,
            model,
            items: List[str],
            unique_field: str
    ) -> Dict[str, object]:
        """
        For a given model and a list of item names/keys (e.g., a list of genres),
        retrieves any existing records in the database matching these items.
        If some items are not found, they are created in bulk. Returns a dictionary
        mapping the item string to the corresponding model instance.

        :param model: The SQLAlchemy model class (e.g., GenreModel).
        :param items: A list of string values to create or retrieve (e.g., ["Comedy", "Action"]).
        :param unique_field: The field name that should be unique (e.g., "name").
        :return: A dict mapping each item to its model instance.
        """
        existing_dict: Dict[str, object] = {}

        if items:
            for i in range(0, len(items), CHUNK_SIZE):
                chunk = items[i: i + CHUNK_SIZE]
                result = await self._db_session.execute(
                    select(model).where(
                        getattr(model, unique_field).in_(chunk))
                )
                existing_in_chunk = result.scalars().all()
                for obj in existing_in_chunk:
                    key = getattr(obj, unique_field)
                    existing_dict[key] = obj

        new_items = [item for item in items if item not in existing_dict]
        new_records = [{unique_field: item} for item in new_items]

        if new_records:
            for i in range(0, len(new_records), CHUNK_SIZE):
                chunk = new_records[i: i + CHUNK_SIZE]
                await self._db_session.execute(insert(model).values(chunk))
                await self._db_session.flush()

            for i in range(0, len(new_items), CHUNK_SIZE):
                chunk = new_items[i: i + CHUNK_SIZE]
                result_new = await self._db_session.execute(
                    select(model).where(
                        getattr(model, unique_field).in_(chunk))
                )
                inserted_in_chunk = result_new.scalars().all()
                for obj in inserted_in_chunk:
                    key = getattr(obj, unique_field)
                    existing_dict[key] = obj

        return existing_dict

    async def _bulk_insert(self, table,
                           data_list: List[Dict[str, int]]) -> None:
        """
        Insert data_list into the given table in chunks, displaying progress via tqdm.

        :param table: The SQLAlchemy table or model to insert into.
        :param data_list: A list of dictionaries, where each dict represents a row to insert.
        """
        total_records = len(data_list)
        if total_records == 0:
            return

        num_chunks = math.ceil(total_records / CHUNK_SIZE)
        table_name = getattr(table, '__tablename__', str(table))

        for chunk_index in tqdm(range(num_chunks),
                                desc=f"Inserting into {table_name}"):
            start = chunk_index * CHUNK_SIZE
            end = start + CHUNK_SIZE
            chunk = data_list[start:end]
            if chunk:
                await self._db_session.execute(insert(table).values(chunk))

        await self._db_session.flush()

    async def _prepare_reference_data(
            self,
            data: pd.DataFrame
    ) -> Tuple[
        Dict[str, object],
        Dict[str, object],
        Dict[str, object],
        Dict[str, object]
    ]:
        """
        Gather unique values for countries, genres, actors, and languages from the DataFrame.
        Then call _get_or_create_bulk for each to ensure they exist in the database.

        :param data: The preprocessed Pandas DataFrame containing movie info.
        :return: A tuple of four dictionaries:
                 (genre_map, actor_map, certificates_map, directors_map).
        """

        genres = {
            genre
            for genres_row in data["Genre"]
            for genre in genres_row.split(",")
        }

        actors = set()
        for col in ["Star1", "Star2", "Star3", "Star4"]:
            actors.update(data[col])

        certificates = set(data["Certificate"])

        directors = set(data["Director"])

        genre_map = await self._get_or_create_bulk(
            GenreModel, list(genres), 'name'
        )
        actor_map = await self._get_or_create_bulk(
            StarModel, list(actors), 'name'
        )
        certificates_map = await self._get_or_create_bulk(
            CertificationModel, list(certificates), 'name'
        )
        directors_map = await self._get_or_create_bulk(
            DirectorModel, list(directors), 'name'
        )
        return genre_map, actor_map, certificates_map, directors_map

    def _prepare_movies_data(
            self,
            data: pd.DataFrame,
            certificates_map: Dict[str, object]
    ) -> List[Dict[str, object]]:
        """
        Build a list of dictionaries representing movie records to be inserted into MovieModel.

        :param data: The preprocessed DataFrame.

        :return: A list of dictionaries, each representing a new movie record.
        """
        movies_data: List[Dict[str, object]] = []
        for _, row in tqdm(
                data.iterrows(), total=data.shape[0], desc="Processing movies"
        ):
            certification = certificates_map[row['Certificate']]
            movie = {
                "name": row['Title'],
                "year": row["Released_Year"],
                "time": row["Runtime"],
                "imdb": row["IMDB_Rating"],
                "votes": row["No_of_Votes"],
                "meta_score": row["Meta_score"],
                "gross": row["Gross"],
                "description": row['Overview'],
                "price": Decimal(f"{random.uniform(1, 100):.2f}"),
                "certification_id": certification.id,
                "users_like": [],
            }
            movies_data.append(movie)
        return movies_data

    def _prepare_associations(
            self,
            data: pd.DataFrame,
            movie_ids: List[int],
            genre_map: Dict[str, object],
            actor_map: Dict[str, object],
            directors_map: Dict[str, object],

    ) -> Tuple[
        List[Dict[str, int]], List[Dict[str, int]], List[Dict[str, int]]
    ]:
        """
        Prepare three lists of dictionaries: movie-genre, movie-actor, and
        associations for all movies in the DataFrame.

        :param data: The DataFrame containing movie info.
        :param movie_ids: The list of newly inserted movie IDs, in the same order as DataFrame rows.
        :param genre_map: A mapping of genre names to GenreModel instances.
        :param actor_map: A mapping of actor names to ActorModel instances.
        :param directors_map: A mapping of director names to DirectorModel instances.
        :return: A tuple of three lists:
                 (movie_genres_data, movie_actors_data, movie_directors_data),
                 each containing dictionaries for bulk insertion.
        """
        movie_genres_data: List[Dict[str, int]] = []
        movie_actors_data: List[Dict[str, int]] = []
        movie_directors_data: List[Dict[str, int]] = []

        for i, (_, row) in enumerate(
                tqdm(data.iterrows(),
                     total=data.shape[0],
                     desc="Processing associations"
                     )):
            movie_id = movie_ids[i]

            for genre_name in row['Genre'].split(','):
                genre_name = genre_name.strip()
                if genre_name:
                    genre = genre_map[genre_name]
                    movie_genres_data.append(
                        {"movie_id": movie_id, "genre_id": genre.id})

            for actor_name in (
                    set([row["Star1"], row["Star2"], row["Star3"], row["Star4"]])
            ):
                if actor_name:
                    actor = actor_map[actor_name]
                    movie_actors_data.append(
                        {"movie_id": movie_id, "star_id": actor.id})

            if row["Director"]:
                director = directors_map[row["Director"]]
                movie_directors_data.append(
                    {"movie_id": movie_id, "director_id": director.id})

        return movie_genres_data, movie_actors_data, movie_directors_data

    async def seed(self) -> None:
        """
        Main method to seed the database with movie data from the CSV.
        It pre-processes the CSV, prepares reference data (countries, genres, actors, languages),
        inserts all movies, then inserts many-to-many relationships (genres, actors, languages).
        """
        try:
            if self._db_session.in_transaction():
                print("Rolling back existing transaction.")
                await self._db_session.rollback()

            await self._seed_user_groups()
            data = self._preprocess_csv()
            genre_map, actor_map, certificates_map, directors_map = await self._prepare_reference_data(
                data)

            movies_data = self._prepare_movies_data(data, certificates_map)

            result = await self._db_session.execute(
                insert(MovieModel).returning(MovieModel.id),
                movies_data
            )
            movie_ids = list(result.scalars().all())

            movie_genres_data, movie_actors_data, movie_directors_map = self._prepare_associations(
                data, movie_ids, genre_map, actor_map, directors_map
            )

            await self._bulk_insert(MoviesGenresModel, movie_genres_data)
            await self._bulk_insert(MoviesStarsModel, movie_actors_data)
            await self._bulk_insert(MoviesDirectorsModel, movie_directors_map)
            await self._db_session.commit()
            print("Seeding completed.")

        except SQLAlchemyError as e:
            print(f"An error occurred: {e}")
            raise
        except Exception as e:
            print(f"Unexpected error: {e}")
            raise


async def main() -> None:
    """
    The main async entry point for running the database seeder.
    Checks if the database is already populated, and if not, performs the seeding process.
    """
    settings = get_settings()
    async with get_db_contextmanager() as db_session:
        seeder = CSVDatabaseSeeder(settings.PATH_TO_MOVIES_CSV, db_session)

        if not await seeder.is_db_populated():
            try:
                await seeder.seed()
                print("Database seeding completed successfully.")
                stmt = select(UserGroupModel.id).where(UserGroupModel.name == "admin")
                result = await db_session.execute(stmt)
                admin_group_id = result.scalars().first()
                super_user = UserModel.create(
                    email=settings.SUPER_USER_EMAIL,
                    raw_password=settings.SUPER_USER_PASSWORD,
                    group_id=admin_group_id
                )
                super_user.is_active = True
                db_session.add(super_user)
                await db_session.commit()
            except Exception as e:
                print(f"Failed to seed the database: {e}")
        else:
            print("Database is already populated. Skipping seeding.")


if __name__ == "__main__":
    asyncio.run(main())
