from __future__ import annotations

import abc
import typing

import hikari

if typing.TYPE_CHECKING:
    from airy.models.bot import Airy


class BaseService(abc.ABC):
    bot: "Airy" = None  # type: ignore
    _is_started: bool = False

    @classmethod
    @abc.abstractmethod
    async def on_startup(cls, event: hikari.StartedEvent):
        pass

    @classmethod
    @abc.abstractmethod
    async def on_shutdown(cls, event: hikari.StoppedEvent = None):
        pass

    @classmethod
    def start(cls, bot: "Airy"):
        cls.bot = bot
        cls._is_started = True
        cls.bot.subscribe(hikari.StartedEvent, cls.on_startup)
        cls.bot.subscribe(hikari.StoppedEvent, cls.on_shutdown)

    @classmethod
    def shutdown(cls, bot: "Airy"):
        cls._is_started = False
        cls.bot.unsubscribe(hikari.StartedEvent, cls.on_startup)
        cls.bot.unsubscribe(hikari.StoppedEvent, cls.on_shutdown)
        bot.create_task(cls.on_shutdown())
