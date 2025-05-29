from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates



router = APIRouter()


templates = Jinja2Templates(directory="notifications/templates")

@router.get(
    "/success/",
    response_class=HTMLResponse
)
async def paid_success(request: Request):
    return templates.TemplateResponse("success_paid.html", {"request": request})


@router.get(
    "/cancel/",
    response_class=HTMLResponse
)
async def paid_canceled(request: Request):
    return templates.TemplateResponse("canceled_paid.html", {"request": request})