
comment_schema_example = {
    "content": "This is amazing movie!"
}

response_commentary_schema_example = {
    "id": 1,
    "content": "Cool movie!",
    "movie_id": 5,
    "user_id": 34,
}

reply_schema_example = {
    "content": "And what do you understand? This movie is a derivative",
    "is_like": False
}

response_reply_schema_example = {
    **response_commentary_schema_example,
    "parent_id": 1,
}