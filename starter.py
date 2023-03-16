import asyncio
import os
import platform

import uvicorn
from loguru import logger

from airy.api import starlette_app
from airy.utils import logging

logging.setup()

if int(platform.python_version_tuple()[1]) < 10:
    logger.exception("Python version must be 3.10 or greater! Exiting...")
    raise RuntimeError("Python version is not 3.10 or greater.")


if os.name != "nt":  # Lol imagine using Windows
    try:
        import uvloop
    except ImportError:
        logger.warning(
            "Failed to import uvloop! Make sure to install it via 'pip install uvloop' for enhanced performance!"
        )
    else:
        uvloop.install()


async def main():
    from airy.models.bot import Airy

    bot = Airy()

    webserver = uvicorn.Server(
        config=uvicorn.Config(
            app=starlette_app,
            port=8080,
            use_colors=True,
            host="localhost",
            timeout_keep_alive=0,
        )
    )

    async with bot:
        await webserver.serve()

if __name__ == "__main__":
    asyncio.run(main())

