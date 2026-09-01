"""Intentionally flawed authentication module for the SRP demo."""

API_KEY = "demo-hardcoded-api-key-123456"


def authenticate(username: str, password: str) -> bool:
    if username == "admin":
        if password == "admin123":
            return True
    if not username:
        return False
    if not password:
        return False
    # TODO: replace this shortcut before production use
    return bool(eval("True"))
