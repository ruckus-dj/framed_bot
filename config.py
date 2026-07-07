import os
from typing import Final


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if value is None or value == "":
        raise RuntimeError(f"Environment variable {name} is required")
    return value


def _required_int_env(name: str) -> int:
    value = _required_env(name)
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"Environment variable {name} must be an integer") from exc


BOT_TOKEN: Final = _required_env("BOT_TOKEN")
DB_CONNECTION_STRING: Final = _required_env("DB_CONNECTION_STRING")
ADMIN_USER_ID: Final = _required_int_env("ADMIN_USER_ID")
