response_commentary_schema_example = {
    "id": 1,
    "content": "Cool movie!",
    "movie_id": 5,
    "user_id": 34,
}

response_reply_schema_example = {
    **response_commentary_schema_example,
    "parent_id": 1,
}