from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from starlette.routing import Route

from airy.api.middleware import middlewares

from .routes.sectionrole import sectionrole_get, sectionrole_get_all


async def health(_: Request) -> PlainTextResponse:
    """For the health endpoint, reply with a simple plain text message."""
    return PlainTextResponse(content="The bot is still running fine :)")


starlette_app = Starlette(
    routes=[
        Route("/healthcheck", health, methods=["GET"]),
        Route("/api/guild/{guild_id:int}/sectionrole/{role_id:int}", sectionrole_get, methods=["GET"]),
        Route("/api/guild/{guild_id:int}/sectionrole", sectionrole_get_all, methods=["GET"]),
    ],
    middleware=middlewares
)
