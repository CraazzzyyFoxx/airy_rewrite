from __future__ import annotations

import typing
import hikari

if typing.TYPE_CHECKING:
    from airy.models.bot import Airy


class BaseService:
    def __init__(self,):
        self.bot: "Airy" = None
        self._is_started: bool = False

    async def on_startup(self, event: hikari.StartedEvent):
        pass

    async def on_shutdown(self, event: hikari.StoppedEvent = None):
        pass

    def start(self, bot: "Airy"):
        self.bot = bot
        self._is_started = True
        self.bot.subscribe(hikari.StartedEvent, self.on_startup)
        self.bot.subscribe(hikari.StoppedEvent, self.on_shutdown)

    def shutdown(self, bot: "Airy"):
        self._is_started = False
        self.bot.unsubscribe(hikari.StartedEvent, self.on_startup)
        self.bot.unsubscribe(hikari.StoppedEvent, self.on_shutdown)
        bot.create_task(self.on_shutdown())
