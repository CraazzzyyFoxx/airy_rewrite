from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.errors import ServerErrorMiddleware
from starlette.middleware.exceptions import ExceptionMiddleware

from pydantic import ValidationError

# from bot.api.middleware.auth import CustomAuthenticationBackend
# from bot.api.middleware.error import validation_error_handler

import config


__all__ = ("middlewares", )

middlewares = [
    Middleware(ServerErrorMiddleware, debug=config.DEBUG),
    Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]),
    # Middleware(AuthenticationMiddleware, backend=CustomAuthenticationBackend()),
    Middleware(ExceptionMiddleware, debug=config.DEBUG)
]
