import secrets

from fastapi import HTTPException, Request, status

CSRF_SESSION_KEY = "csrf_token"


def get_csrf_token(request: Request) -> str:
    """Return the session CSRF token, creating one if absent."""
    token = request.session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        request.session[CSRF_SESSION_KEY] = token
    return token


async def verify_csrf(request: Request) -> None:
    """Dependency for SSR POST handlers: validate the submitted CSRF token."""
    form = await request.form()
    submitted = form.get("csrf_token")
    expected = request.session.get(CSRF_SESSION_KEY)
    if not expected or not submitted or not secrets.compare_digest(str(submitted), str(expected)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token invalid")
