from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db


from routes.crud.payments import get_users_payments
from routes.utils import get_required_access_token_payload
from schemas import AccessTokenPayload, PaymentsHistorySchema, PaymentSchema


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

    payments_list = await get_users_payments(user_id=user_id, db=db)
    data = {"payments": payments_list}
    return  PaymentsHistorySchema.model_validate(data)
