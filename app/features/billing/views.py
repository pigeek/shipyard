from fastapi import APIRouter, Depends, Request

from app.features.users.dependencies import load_current_user
from app.web.templating import render

router = APIRouter(tags=["billing-ssr"])


@router.get("/billing/success")
async def checkout_success(request: Request, _state=Depends(load_current_user)):
    return render(
        request,
        "billing/result.html",
        {"heading": "Payment successful", "message": "Thanks — your subscription is active."},
    )


@router.get("/billing/cancel")
async def checkout_cancel(request: Request, _state=Depends(load_current_user)):
    return render(
        request,
        "billing/result.html",
        {"heading": "Checkout cancelled", "message": "No charge was made."},
    )
