import pytest
from app.core.config import Settings
from app.features.users import manager
from pydantic import ValidationError


def test_default_enables_both_transports():
    backends = {b.name for b in manager._enabled_backends()}
    assert backends == {"jwt", "cookie"}


def test_bearer_only_drops_cookie_backend(monkeypatch):
    monkeypatch.setattr(manager.settings, "auth_cookie_enabled", False)
    monkeypatch.setattr(manager.settings, "auth_bearer_enabled", True)
    assert {b.name for b in manager._enabled_backends()} == {"jwt"}


def test_cookie_only_drops_bearer_backend(monkeypatch):
    monkeypatch.setattr(manager.settings, "auth_cookie_enabled", True)
    monkeypatch.setattr(manager.settings, "auth_bearer_enabled", False)
    assert {b.name for b in manager._enabled_backends()} == {"cookie"}


def test_disabling_both_transports_is_rejected():
    with pytest.raises(ValidationError):
        Settings(auth_cookie_enabled=False, auth_bearer_enabled=False)
