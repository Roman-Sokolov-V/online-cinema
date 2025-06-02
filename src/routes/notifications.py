from fastapi import APIRouter, Request, Depends, Path
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from config import get_email_notificator
from database import UserModel, OrderModel
from notifications import EmailSenderInterface

router = APIRouter()


templates = Jinja2Templates(directory="notifications/templates")

@router.get(
    "/success/{order_id}/",
    summary="Successful payment",
    description="Shows html page with successful payment notification, and "
                "send the same email",
    response_class=HTMLResponse
)
async def paid_success(
        request: Request,
        order_id: int = Path(..., ge=1),
        email_sender: EmailSenderInterface = Depends(get_email_notificator),
        db: AsyncSession = Depends(get_db)
) -> HTMLResponse:
    stmt = (
        select(UserModel)
        .join(UserModel.orders)
        .where(OrderModel.id == order_id)
        .options(joinedload(UserModel.orders))
    )
    result = await db.execute(stmt)
    user = result.scalars().first()
    if user is not None:
        await email_sender.send_payments_status(
            email=user.email,
            payments_status="successful",
        )
        return templates.TemplateResponse(
            "success_paid.html", {"request": request}
        )
    return HTMLResponse(
        status_code=400, content="User not found for this order."
    )


@router.get(
    "/cancel/{order_id}/",
    summary="Canceled payment",
    description="Shows html page with notification about canceled payment, "
                "and send the same email",
    response_class=HTMLResponse
)
async def paid_canceled(
        request: Request,
        order_id: int = Path(..., ge=1),
        email_sender: EmailSenderInterface = Depends(get_email_notificator),
        db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(UserModel)
        .join(UserModel.orders)
        .where(OrderModel.id == order_id)
        .options(joinedload(UserModel.orders))
    )
    result = await db.execute(stmt)
    user = result.scalars().first()
    if user is not None:
        await email_sender.send_payments_status(
            email=user.email,
            payments_status="canceled",
        )
        return templates.TemplateResponse(
            "canceled_paid.html", {"request": request}
        )
    return HTMLResponse(
        status_code=400, content="User not found for this order."
    )
