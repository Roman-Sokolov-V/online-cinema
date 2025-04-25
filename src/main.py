from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import (
    movie_router,
    accounts_router,
    profiles_router
)

app = FastAPI(
    title="Movies homework",
    description="Description of project"
)

origins = [
    "http://localhost:8025",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


api_version_prefix = "/api/v1"

app.include_router(accounts_router, prefix=f"{api_version_prefix}/accounts", tags=["accounts"])
app.include_router(profiles_router, prefix=f"{api_version_prefix}/profiles", tags=["profiles"])
app.include_router(movie_router, prefix=f"{api_version_prefix}/theater", tags=["theater"])
