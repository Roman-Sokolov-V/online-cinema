from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select,func
from urllib.parse import urlencode


from database import get_db, PaymentModel

from routes.crud.payments import get_users_payments, get_filtered_stmt, \
    paginate_stmt
from routes.permissions import is_moderator_or_admin_group
from routes.utils import get_required_access_token_payload
from schemas import (
    AccessTokenPayload,
    PaymentsHistorySchema,
    PaymentSchema,
    PaymentsFilterParams,
    AllUsersPaymentsSchema,
)

router = APIRouter()

@router.get(
    "/",
    response_model=PaymentsHistorySchema,
    summary="Payments history",
    description="Endpoint to retrieve payments history",
    status_code=200,
)
async def get_payments_history(
        token_payload: AccessTokenPayload = Depends(
            get_required_access_token_payload
        ),
        db: AsyncSession = Depends(get_db),
):
    user_id = token_payload["user_id"]

    payments_list = await get_users_payments(db=db, user_id=user_id)
    data = {"payments": payments_list}
    return  PaymentsHistorySchema.model_validate(data)


@router.get(
    "/all/",
    dependencies=[Depends(is_moderator_or_admin_group)],
    response_model=AllUsersPaymentsSchema,
    summary="All users payments",
    description="Endpoint to retrieve all users payments, for staff only,"
                "with pagination and filtering by date of creation, users "
                "and status",
    status_code=200,
)
async def get_all_payments(
        request: Request,
        query: Annotated[PaymentsFilterParams, Query()],
        db: AsyncSession = Depends(get_db),
):

    filtered_stmt = get_filtered_stmt(filtered_query=query)

    count_stmt = select(func.count()).select_from(filtered_stmt.subquery())
    result = await db.execute(count_stmt)
    items = result.scalar()
    if items is None:
        items = 0

    paginated_stmt = paginate_stmt(stmt=filtered_stmt, filtered_query=query)
    result = await db.execute(paginated_stmt.order_by(PaymentModel.created_at.desc()))
    payments_list = result.scalars().all()

    next_query = query.model_copy()
    prev_query = query.model_copy()
    if query.offset + query.limit < items:  # type: ignore
        next_query.offset = query.offset + query.limit
    else:
        next_query.offset = query.offset
    if query.offset >= query.limit:
        prev_query.offset = query.offset - query.limit
    else:
        prev_query.offset = 0

    next_page = f"{request.url.path}?{urlencode(next_query.model_dump(mode='json'))}"
    prev_page = f"{request.url.path}?{urlencode(prev_query.model_dump(mode='json'))}"

    return AllUsersPaymentsSchema(
        payments=[
            PaymentSchema.model_validate(payment)
            for payment
            in payments_list
        ],
        prev_page=prev_page,
        next_page=next_page,
        items=items
    )
