from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import (
    movie_router,
    accounts_router,
    profiles_router,
    genres_router,
    actors_router,
    favorites_router,
    shopping_cart_router,
    orders_router,
    webhooks_router,
    notifications_router
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
app.include_router(genres_router, prefix=f"{api_version_prefix}/theater", tags=["genres"])
app.include_router(actors_router, prefix=f"{api_version_prefix}/theater", tags=["actors"])
app.include_router(favorites_router, prefix=f"{api_version_prefix}/opinions", tags=["opinions"])
app.include_router(shopping_cart_router, prefix=f"{api_version_prefix}/cart", tags=["cart"])
app.include_router(orders_router, prefix=f"{api_version_prefix}/orders", tags=["order"])
app.include_router(webhooks_router, prefix=f"{api_version_prefix}/webhooks", tags=["webhooks"])
app.include_router(notifications_router, prefix=f"{api_version_prefix}/notifications", tags=["notifications"])