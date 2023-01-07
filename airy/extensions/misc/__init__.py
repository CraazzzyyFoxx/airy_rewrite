
import logging

import hikari
import lightbulb
from lightbulb import plugins

from airy.models.bot import Airy
from airy.models import AirySlashContext
from airy.static import ColorEnum

misc = plugins.Plugin("Misc")

logger = logging.getLogger(__name__)


@misc.command
@lightbulb.command("ping", "Check the bot's latency.")
@lightbulb.implements(lightbulb.SlashCommand)
async def ping(ctx: AirySlashContext) -> None:
    embed = hikari.Embed(
        title="🏓 Pong!",
        description=f"Latency: `{round(ctx.app.heartbeat_latency * 1000)}ms`",
        color=ColorEnum.MISC,
    )
    await ctx.respond(embed=embed)


def load(bot: Airy) -> None:
    bot.add_plugin(misc)


def unload(bot: Airy) -> None:
    bot.remove_plugin(misc)
