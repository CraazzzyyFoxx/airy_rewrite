from __future__ import annotations

import asyncio
import importlib
import os
import pathlib
import sys
import typing as t

from abc import ABC
from importlib import util

import hikari
import lightbulb
import miru

from hikari.internal import aio
from loguru import logger
from tortoise import Tortoise

from airy.models.context import *
from airy.models import errors
from airy.models.db.impl import Database

import config


class _ServiceT(t.Protocol):
    def load(self, bot: lightbulb.BotApp) -> None:
        ...

    def unload(self, bot: lightbulb.BotApp) -> None:
        ...


class Airy(lightbulb.BotApp, ABC):
    def __init__(self):
        intents = (
                hikari.Intents.GUILDS
                | hikari.Intents.GUILD_MEMBERS
                | hikari.Intents.GUILD_BANS
                | hikari.Intents.GUILD_EMOJIS
                | hikari.Intents.GUILD_INVITES
                | hikari.Intents.ALL_MESSAGE_REACTIONS
                | hikari.Intents.ALL_MESSAGES
                | hikari.Intents.MESSAGE_CONTENT
        )
        super(Airy, self).__init__(
            config.bot.token,
            prefix="dev",
            default_enabled_guilds=config.bot.dev_guilds if config.bot.dev_mode else (),
            intents=intents,
            help_slash_command=False,
            logs=None,
            banner=None,
            cache_settings=hikari.impl.config.CacheSettings(
                components=hikari.api.CacheComponents.ALL,
                max_messages=1000,
            ),

        )
        self.base_dir: pathlib.Path = pathlib.Path(__file__).parent.parent  # type: ignore
        """Bots base directory"""
        self._user_id: t.Optional[hikari.Snowflake] = None
        """Bot ID"""
        self._initial_guilds: t.List[hikari.Snowflake] = []
        """Available Guilds"""
        self._started = asyncio.Event()
        self._is_started = False
        """Bot startup status"""
        self.skip_first_db_backup = True
        """Set too False to back up DB on bot startup too"""
        self._config = config.bot
        """Bot config"""
        self.db = Database(self)

        self.services: t.List[str] = []
        """A list of the currently loaded services."""
        self._current_service: t.Optional[_ServiceT] = None

        miru.install(self)
        self.create_subscriptions()

    @property
    def config(self) -> config.BotConfig:
        return self._config

    @property
    def user_id(self) -> hikari.Snowflake:
        """The application user's ID."""
        if self._user_id is None:
            raise hikari.ComponentStateConflictError("The bot is not yet initialized, user_id is unavailable.")

        return self._user_id

    @property
    def is_ready(self) -> bool:
        """Indicates if the application is ready to accept instructions or not.
        Alias for BotApp.is_alive"""
        return self.is_alive

    @property
    def is_started(self) -> bool:
        """Boolean indicating if the bot has started up or not."""
        return self._is_started

    async def wait_until_started(self) -> None:
        """
        Wait until the bot has started up
        """
        await asyncio.wait_for(self._started.wait(), timeout=None)

    def create_subscriptions(self):
        self.subscribe(hikari.StartingEvent, self.on_starting)
        self.subscribe(hikari.StartedEvent, self.on_started)
        self.subscribe(hikari.StoppingEvent, self.on_stopping)
        self.subscribe(hikari.StoppedEvent, self.on_stop)
        self.subscribe(lightbulb.LightbulbStartedEvent, self.on_lightbulb_started)
        self.subscribe(hikari.GuildAvailableEvent, self.on_guild_available)
        self.subscribe(hikari.GuildJoinEvent, self.on_guild_join)
        self.subscribe(hikari.GuildLeaveEvent, self.on_guild_leave)
        self.subscribe(hikari.MessageCreateEvent, self.on_message)

    ##############
    # EXTENSIONS #
    ##############

    @staticmethod
    def check_path(*paths: t.Union[str, pathlib.Path]):
        path = paths[0]

        if isinstance(path, str):
            path = pathlib.Path(path)

        try:
            path = path.resolve().relative_to(pathlib.Path.cwd())
        except ValueError:
            raise ValueError(f"'{path}' must be relative to the working directory") from None

        if not path.is_dir():
            raise FileNotFoundError(f"'{path}' is not an existing directory")

        return path

    def load_extensions_from(
            self, *paths: t.Union[str, pathlib.Path], recursive: bool = False, must_exist: bool = True
    ) -> None:
        if len(paths) > 1 or not paths:
            for path_ in paths:
                self.load_extensions_from(path_, recursive=recursive, must_exist=must_exist)
            return

        path = self.check_path(*paths)

        for ext_path in path.iterdir():
            if ext_path.is_dir():
                try:
                    ext = str(ext_path.with_suffix("")).replace(os.sep, ".")
                    self.load_extensions(ext)
                except lightbulb.errors.ExtensionMissingLoad:
                    pass

        logger.info("Extensions loaded")

    ############
    # SERVICES #
    ############

    def load_service(self, *extensions: str) -> None:
        if len(extensions) > 1 or not extensions:
            for service in extensions:
                self.load_service(service)
            return
        service = extensions[0]

        if service in self.extensions:
            raise errors.ServiceAlreadyLoaded(f"Service {service!r} is already loaded.")

        spec = util.find_spec(service)
        if spec is None:
            raise errors.ServiceNotFound(f"No service by the name {service!r} was found")

        module = importlib.import_module(service)

        srv = t.cast(_ServiceT, module)
        self._current_service = srv

        if not hasattr(module, "load"):
            logger.error("Service {} not loaded", module)
        else:
            srv.load(self)
            self.services.append(service)
            logger.info("Service loaded {}", service)
        self._current_service = None

    def unload_service(self, *services: str) -> None:
        if len(services) > 1 or not services:
            for service in services:
                self.unload_service(service)
            return
        service = services[0]

        if service not in self.services:
            raise errors.ServiceNotLoaded(f"Service {service!r} is not loaded.")

        try:
            module = importlib.import_module(service)
        except ModuleNotFoundError:
            raise errors.ServiceNotFound(f"No service by the name {service!r} was found") from None

        srv = t.cast(_ServiceT, module)
        self._current_service = srv

        if not hasattr(module, "unload"):
            raise errors.ServiceMissingUnload(f"Service {service!r} is missing an unload function")
        else:
            srv.unload(self)
            self.services.remove(service)
            del sys.modules[service]
            logger.info(f"Service unloaded {service!r}")
        self._current_service = None

    def reload_service(self, *services: str) -> None:
        if len(services) > 1 or not services:
            for service in services:
                self.reload_service(service)
            return
        service = services[0]
        try:
            old = sys.modules[service]
        except KeyError:
            raise errors.ServiceNotLoaded(f"Service {service!r} is not loaded.")
        try:
            module = importlib.import_module(service)
            importlib.reload(module)
        except Exception as e:
            sys.modules[service] = old
            if not isinstance(e, errors.ServiceAlreadyLoaded):
                self.load_service(service)
            raise e
        else:
            del old

    def load_services_from(
            self, *paths: t.Union[str, pathlib.Path], recursive: bool = False, must_exist: bool = True
    ) -> None:
        if len(paths) > 1 or not paths:
            for path_ in paths:
                self.load_services_from(path_, recursive=recursive, must_exist=must_exist)
            return

        path = self.check_path(*paths)

        for ext_path in path.iterdir():
            if ext_path.is_dir():
                try:
                    ext = str(ext_path.with_suffix("")).replace(os.sep, ".")
                    self.load_service(ext)
                except errors.ServiceMissingLoad:
                    pass

        logger.info("Services started")

    ############################
    # COMMAND HANDLER (CUSTOM) #
    ############################

    async def get_slash_context(
            self,
            event: hikari.InteractionCreateEvent,
            command: lightbulb.SlashCommand,
            cls: t.Type[lightbulb.SlashContext] = AirySlashContext,
    ) -> AirySlashContext:
        return await super().get_slash_context(event, command, cls)  # type: ignore

    async def get_user_context(
            self,
            event: hikari.InteractionCreateEvent,
            command: lightbulb.UserCommand,
            cls: t.Type[lightbulb.UserContext] = AiryUserContext,
    ) -> AiryUserContext:
        return await super().get_user_context(event, command, cls)  # type: ignore

    async def get_message_context(
            self,
            event: hikari.InteractionCreateEvent,
            command: lightbulb.MessageCommand,
            cls: t.Type[lightbulb.MessageContext] = AiryMessageContext,
    ) -> AiryMessageContext:
        return await super().get_message_context(event, command, cls)  # type: ignore

    async def get_prefix_context(
            self, event: hikari.MessageCreateEvent, cls: t.Type[lightbulb.PrefixContext] = AiryPrefixContext
    ) -> t.Optional[AiryPrefixContext]:
        return await super().get_prefix_context(event, cls)  # type: ignore

    ##########
    # EVENTS #
    ##########

    async def on_starting(self, _: hikari.StartingEvent) -> None:
        # loop.create_task(self.http_server.start())
        await self.db.connect()
        await Tortoise.init(config.tortoise_config)
        self.load_services_from("./airy/services")
        self.load_extensions_from("./airy/extensions")

    async def on_started(self, _: hikari.StartedEvent) -> None:
        user = self.get_me()
        self._user_id = user.id if user else None

        logger.info(f"Startup complete, initialized as {user}.")
        activity = hikari.Activity(name="@Airy", type=hikari.ActivityType.LISTENING)
        await self.update_presence(activity=activity)

        if config.bot.dev_mode:
            logger.warning("Developer mode is enabled!")

    async def on_stopping(self, _: hikari.StoppingEvent) -> None:
        self.unload_service(*self.services)
        logger.info("Bot is shutting down...")

    async def on_stop(self, _: hikari.StoppedEvent) -> None:
        await self.db.close()
        await Tortoise.close_connections()

    async def on_guild_available(self, event: hikari.GuildAvailableEvent) -> None:
        if self.is_started:
            return
        self._initial_guilds.append(event.guild_id)

    async def on_lightbulb_started(self, _: lightbulb.LightbulbStartedEvent) -> None:

        # Insert all guilds the bot is member of into the db global config on startup
        async with self.db.acquire() as con:
            await con.executemany(
                """ INSERT INTO guild (guild_id) VALUES ($1)
                    ON CONFLICT (guild_id) DO NOTHING""",
                [(guild_id, ) for guild_id in self._initial_guilds],
            )
            logger.info(f"Connected to {len(self._initial_guilds)} guilds.")
            self._initial_guilds = []

        # Set this here so all guild_ids are in DB
        self._started.set()
        self._is_started = True
        self.unsubscribe(hikari.GuildAvailableEvent, self.on_guild_available)

    async def on_message(self, event: hikari.MessageCreateEvent) -> None:
        if not event.content:
            return

        if self.is_ready and event.is_human:
            mentions = [f"<@{self.user_id}>", f"<@!{self.user_id}>"]

            if event.content in mentions:
                embed = hikari.Embed(
                    title="Hi!",
                    description="Use `/` to access my commands and see what I can do!",
                    color=0xFEC01D,
                )
                user = self.get_me()
                embed.set_thumbnail(user.avatar_url if user else None)
                await event.message.respond(embed=embed)
                return

    async def on_guild_join(self, event: hikari.GuildJoinEvent) -> None:
        """Guild join behaviour"""
        await self.db.execute(
            "INSERT INTO guild (guild_id) VALUES ($1) ON CONFLICT (guild_id) DO NOTHING", event.guild_id
        )

        if event.guild.system_channel_id is None:
            return

        me = event.guild.get_member(self.user_id)
        channel = event.guild.get_channel(event.guild.system_channel_id)

        assert me is not None
        assert isinstance(channel, hikari.PermissibleGuildChannel)

        if not channel or not (hikari.Permissions.SEND_MESSAGES & lightbulb.utils.permissions_in(channel, me)):
            return

        try:
            await channel.send(
                embed=hikari.Embed(
                    title="Beep Boop!",
                    description="""I have been summoned to this server. Type `/` to see what I can do!\n\n""",
                    color=0xFEC01D,
                ).set_thumbnail(me.avatar_url)
            )
        except hikari.ForbiddenError:
            pass
        logger.info(f"Bot has been added to new guild: {event.guild.name} ({event.guild_id}).")

    async def on_guild_leave(self, event: hikari.GuildLeaveEvent) -> None:
        """Guild removal behaviour"""
        await self.db.wipe_guild(event.guild_id, keep_record=False)
        logger.info(f"Bot has been removed from guild {event.guild_id}, correlating data erased.")

    async def __aenter__(self):
        if self._closed_event:
            raise hikari.errors.ComponentStateConflictError("bot is already running")

        # if shard_ids is not None and shard_count is None:
        #     raise TypeError("'shard_ids' must be passed with 'shard_count'")
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        loop = aio.get_or_make_loop()
        if self._closing_event:
            if self._closing_event.is_set():
                await self._closing_event.wait()
            else:
                await self.close()

        logger.info("successfully terminated")
