from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, StarModel
from routes.permissions import is_moderator_or_admin
from schemas import StarCreateSchema, StarSchema, StarListSchema

router = APIRouter()


@router.post(
    "/actors/",
    dependencies=[Depends(is_moderator_or_admin)],
    response_model=StarSchema,
    summary="Create an actor",
    description=(
            "This endpoint allows moderators and admins to add actors"
            " to the database."
    ),
    responses={
        201: {
            "description": "The actor has been created",
        },
        409: {
            "description": "Invalid input.",
            "content": {
                "application/json": {
                    "example": {"detail": "Actor with given name already exists."}
                }
            },
        },
        403: {
            "description": ("Request user do not has permissions to use this "
                            "endpoint. Only admins and moderators can add actors."),
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Access denied, not enough permissions"}
                }
            }
        }
    },
    status_code=201
)
async def create_actor(
        actor_data: StarCreateSchema,
        db: AsyncSession = Depends(get_db)
) -> StarSchema:
    actor = await db.scalar(select(StarModel).where(
        StarModel.name == actor_data.name)
    )
    if actor:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Actor with given name already exists."
        )
    actor = StarModel(**actor_data.model_dump())
    db.add(actor)
    await db.commit()
    await db.refresh(actor)
    return StarSchema.model_validate(actor)


@router.get(
    "/actors/",
    response_model=StarListSchema,
    summary="Get list of actors",
    description=("<h3>This endpoint allows all users to get a list of actors.</h3>"),
    status_code=200
)
async def get_actors(
        db: AsyncSession = Depends(get_db)
) -> StarListSchema:
    stmt = select(StarModel)
    result = await db.execute(stmt)
    stars = result.scalars().all()
    stars_list = [StarSchema.model_validate(star) for star in stars]
    return StarListSchema(stars=stars_list)


@router.delete(
    "/actors/{star_id}/",
    dependencies=[Depends(is_moderator_or_admin)],
    summary="Delete a actor",
    description=(
            "<h3>Delete a specific star from the database by its unique ID.</h3>"
            "<p>If the actor exists, it will be deleted. If it does not exist, "
            "a 404 error will be returned.</p>"
    ),
    responses={
        204: {
            "description": "Actor deleted successfully.",
        },
        404: {
            "description": "Actor not found.",
            "content": {
                "application/json": {
                    "example": {"detail": "Actor with the given ID was not found."}
                }
            }
        },
        403: {
            "description": ("Request user do not has permissions to use this "
                            "endpoint. Only admins and moderators can add actors."),
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Access denied, not enough permissions"}
                }
            }
        },
    },
    status_code=204
)
async def delete_star(
        star_id: int,
        db: AsyncSession = Depends(get_db)
):
    stmt = select(StarModel).where(StarModel.id == star_id)
    result = await db.execute(stmt)
    star = result.scalars().first()

    if not star:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Actor with the given ID was not found."
        )
    await db.delete(star)
    await db.commit()
    return {"detail": "Actor deleted successfully."}

@router.patch(
    "/actors/{star_id}/",
    dependencies=[Depends(is_moderator_or_admin)],
    summary="Update a actor",
    description=("<h3>Update a specific actor from the database by its unique ID.</h3>"),
    responses={
        200: {
            "description": "Actor updated successfully.",
            "content": {
                "application/json": {
                    "example": {"detail": "Actor updated successfully."}
                }
            }
        },
        404: {
            "description": "Actor with the given ID was not found.",
            "content": {
                "application/json": {
                    "example": {"detail": "Actor with the given ID was not found."}
                }
            }
        },
        409: {
            "description": "Invalid input.",
            "content": {
                "application/json": {
                    "example": {"detail": "Actor with given name already exists."}
                }
            },
        },
        403: {
            "description": ("Request user do not has permissions to use this "
                            "endpoint. Only admins and moderators can add actors."),
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Access denied, not enough permissions"}
                }
            }
        },
    }
)
async def update_actor(
        star_id: int,
        star_data: StarCreateSchema,
        db: AsyncSession = Depends(get_db)
) -> StarSchema:
    stmt = select(StarModel).where(StarModel.name == star_data.name)
    result = await db.execute(stmt)
    star_with_given_new_name = result.scalars().first()
    if star_with_given_new_name:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Actor with given name already exists."
        )

    star = await db.scalar(select(StarModel).where(StarModel.id == star_id))
    if not star:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Actor with the given ID was not found."
        )
    star.name = star_data.name
    await db.commit()
    await db.refresh(star)
    return StarSchema.model_validate(star)
