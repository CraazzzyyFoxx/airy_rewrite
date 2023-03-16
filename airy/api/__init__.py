from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from starlette.routing import Route


from airy.api.middleware import middlewares


async def health(_: Request) -> PlainTextResponse:
    """For the health endpoint, reply with a simple plain text message."""
    return PlainTextResponse(content="The bot is still running fine :)")

starlette_app = Starlette(
    routes=[
        Route("/healthcheck", health, methods=["GET"]),
    ],
    middleware=middlewares
)
