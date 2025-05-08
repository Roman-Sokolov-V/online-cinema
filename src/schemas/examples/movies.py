genre_schema_example = {
    "id": 1,
    "genre": "Comedy"
}

star_schema_example = {
    "id": 1,
    "name": "Jimmy Fallon"
}

director_schema_example = {
    "id": 1,
    "name": "Steven Spielberg"
}

movie_item_schema_example = {
    "id": 9933,
    "name": "The Swan Princess: A Royal Wedding",
    "date": 2020,
    "time": 102,
    "imdb": 7.8,
    "votes": 2365,
    "meta_score": 5.8,
    "gross": 1000000.00,
    "description": "Princess Odette and Prince Derek are going to a wedding at Princess Mei Li and her beloved Chen. "
                "But evil forces are at stake and the wedding plans are tarnished and "
                "true love has difficult conditions.",
    "price": 8.99,
    "certification_id": 3,
    "genres": genre_schema_example,
    "stars": star_schema_example,
    "directors": director_schema_example
}

movie_list_response_schema_example = {
    "movies": [
        movie_item_schema_example
    ],
    "prev_page": "/theater/movies/?page=1&per_page=1",
    "next_page": "/theater/movies/?page=3&per_page=1",
    "total_pages": 9933,
    "total_items": 9933
}

movie_create_schema_example = {
    "name": "New Movie",
    "year": 2023,
    "time": 102,
    "imdb": 8.5,
    "votes": 890,
    "meta_score": 45.3,
    "gross": 1000000.00,
    "description": "An amazing movie.",
    "price": 9.99,
    "certification_name": "pg-13",
    "genres": ["action", "adventure"],
    "stars": ["Rutger Hauer", "Jeff Cohen"],
    "directors": ["Steven Spielberg", "Peter Weir"]
}



movie_detail_schema_example = {
    **movie_item_schema_example,
    "stars": [star_schema_example],
    "genres": [genre_schema_example],
    "directors": [director_schema_example]
}

movie_update_schema_example = {
    "name": "New Movie",
    "year": 2023,
    "time": 102,
    "imdb": 8.5,
    "votes": 890,
    "meta_score": 45.3,
    "gross": 1000000.00,
    "description": "An amazing movie.",
    "price": 9.99,
    "certification_name": "pg-13",
    "genres": ["action", "adventure"],
    "stars": ["Rutger Hauer", "Jeff Cohen"],
    "directors": ["Steven Spielberg", "Peter Weir"]
}
