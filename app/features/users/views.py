from fastapi import APIRouter, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_users.authentication import JWTStrategy
from fastapi_users.exceptions import (
    InvalidResetPasswordToken,
    InvalidVerifyToken,
    UserAlreadyExists,
    UserAlreadyVerified,
    UserInactive,
)
from starlette.responses import RedirectResponse

from app.core.config import settings
from app.features.users.dependencies import (
    load_current_user,
    ssr_required_user,
)
from app.features.users.manager import UserManager, get_user_manager
from app.features.users.models import User
from app.features.users.schemas import UserCreate
from app.features.users.security import COOKIE_NAME, get_jwt_strategy
from app.web.csrf import verify_csrf
from app.web.templating import render

router = APIRouter(tags=["users-ssr"])


def _safe_next(value: str | None) -> str:
    """Only allow local, single-slash redirect targets (avoid open redirects)."""
    if value and value.startswith("/") and not value.startswith("//"):
        return value
    return "/"


def _set_auth_cookie(response: RedirectResponse, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=settings.access_token_lifetime_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


@router.get("/auth/login")
async def login_form(request: Request, next: str = "/", user=Depends(load_current_user)):
    if user is not None:
        return RedirectResponse(_safe_next(next), status_code=303)
    return render(request, "users/login.html", {"next": _safe_next(next)})


@router.post("/auth/login")
async def login_submit(
    request: Request,
    _csrf: None = Depends(verify_csrf),
    manager: UserManager = Depends(get_user_manager),
    strategy: JWTStrategy = Depends(get_jwt_strategy),
):
    form = await request.form()
    next_url = _safe_next(str(form.get("next", "/")))
    credentials = OAuth2PasswordRequestForm(
        username=str(form.get("email", "")), password=str(form.get("password", ""))
    )
    user = await manager.authenticate(credentials)
    if user is None or not user.is_active:
        return render(
            request,
            "users/login.html",
            {
                "flash": "Invalid email or password.",
                "flash_level": "error",
                "next": next_url,
            },
            status_code=400,
        )
    token = await strategy.write_token(user)
    response = RedirectResponse(next_url, status_code=303)
    _set_auth_cookie(response, token)
    return response


@router.post("/auth/logout")
async def logout(
    request: Request,
    _csrf: None = Depends(verify_csrf),
    manager: UserManager = Depends(get_user_manager),
    strategy: JWTStrategy = Depends(get_jwt_strategy),
):
    # Revoke the session token server-side, then clear the cookie.
    token = request.cookies.get(COOKIE_NAME)
    if token:
        user = await strategy.read_token(token, manager)
        if user is not None:
            await strategy.destroy_token(token, user)
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response


@router.get("/auth/register")
async def register_form(request: Request, user=Depends(load_current_user)):
    if user is not None:
        return RedirectResponse("/", status_code=303)
    return render(request, "users/register.html")


@router.post("/auth/register")
async def register_submit(
    request: Request,
    _csrf: None = Depends(verify_csrf),
    manager: UserManager = Depends(get_user_manager),
    strategy: JWTStrategy = Depends(get_jwt_strategy),
):
    form = await request.form()
    email = str(form.get("email", ""))
    password = str(form.get("password", ""))
    try:
        user = await manager.create(UserCreate(email=email, password=password), request=request)
    except UserAlreadyExists:
        return render(
            request,
            "users/register.html",
            {"flash": "That email is already registered.", "flash_level": "error"},
            status_code=400,
        )
    except Exception:  # password policy / validation
        return render(
            request,
            "users/register.html",
            {"flash": "Could not create account. Check your details.", "flash_level": "error"},
            status_code=400,
        )
    token = await strategy.write_token(user)
    response = RedirectResponse("/", status_code=303)
    _set_auth_cookie(response, token)
    return response


@router.get("/auth/verify")
async def verify_email(
    request: Request,
    token: str = "",
    manager: UserManager = Depends(get_user_manager),
):
    """Click-through email verification landing page (Phase 7.6)."""
    verified = False
    message = "This verification link is invalid or has expired."
    if token:
        try:
            await manager.verify(token)
            verified = True
            message = "Your email is verified — you can now log in."
        except UserAlreadyVerified:
            verified = True
            message = "Your email was already verified."
        except (InvalidVerifyToken, UserInactive):
            pass
    return render(
        request,
        "users/verify.html",
        {"verified": verified, "message": message},
        status_code=200 if verified else 400,
    )


@router.get("/auth/reset")
async def reset_form(request: Request, token: str = ""):
    """Password-reset landing page reached from the email link (Phase 7.6)."""
    return render(request, "users/reset.html", {"token": token})


@router.post("/auth/reset")
async def reset_submit(
    request: Request,
    _csrf: None = Depends(verify_csrf),
    manager: UserManager = Depends(get_user_manager),
):
    form = await request.form()
    token = str(form.get("token", ""))
    password = str(form.get("password", ""))
    try:
        await manager.reset_password(token, password)
    except (InvalidResetPasswordToken, UserInactive):
        return render(
            request,
            "users/reset.html",
            {"token": token, "flash": "This reset link is invalid or has expired."},
            status_code=400,
        )
    except Exception:  # password policy / validation
        return render(
            request,
            "users/reset.html",
            {"token": token, "flash": "Could not reset password. Check your new password."},
            status_code=400,
        )
    return render(request, "users/reset.html", {"done": True})


@router.get("/users/me")
async def profile(request: Request, user: User = Depends(ssr_required_user)):
    return render(request, "users/me.html", {"user": user})
