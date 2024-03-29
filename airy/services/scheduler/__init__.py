from __future__ import annotations

import asyncio
import copy
import datetime
import re
import traceback
import typing

import dateparser  # type: ignore
import hikari

from hikari.internal.enums import Enum
from loguru import logger
from tortoise.expressions import Q

from airy.models.db import DatabaseUser
from airy.services.scheduler.events import BaseTimerEvent, timers_dict_enum_to_class
from airy.services.scheduler.models import DatabaseTimer, TimerEnum
from airy.utils.tasks import IntervalLoop
from airy.utils.time import utcnow

if typing.TYPE_CHECKING:
    from airy.models.bot import Airy

__all__ = ("ConversionMode",
           "SchedulerService")

BaseTimerEventT = typing.TypeVar('BaseTimerEventT', bound=BaseTimerEvent)


class ConversionMode(int, Enum):
    """All possible time conversion modes."""

    RELATIVE = 0
    ABSOLUTE = 1


class SchedulerServiceT:
    """
    All timer-related functionality, including time conversion from strings,
    creation, scheduling & dispatching of timers.
    Essentially the internal scheduler of the bot.
    """

    def __init__(self):
        self.app: Airy | None = None
        self._is_started: bool = False
        self._current_timer: DatabaseTimer | None = None  # Currently, active timer that is being awaited
        self._current_task: asyncio.Task | None = None  # Current task that is handling current_timer
        self._timer_loop: IntervalLoop | None = None

    def current_timer(self):
        return self._current_timer

    async def setup(self, event: hikari.StartedEvent):
        self.start(event.app)  # type: ignore

    def start(self, app: "Airy") -> None:
        """
        Start the scheduler.
        """
        self.app = app
        self._timer_loop = IntervalLoop(self._wait_for_active_timers, hours=1.0)
        self._timer_loop.start()
        self._is_started = True
        logger.info("Scheduler startup complete.")

    def restart(self) -> None:
        """
        Restart the scheduler.
        """
        self._is_started = False
        if self._current_task is not None:
            self._current_task.cancel()
        self._current_task = None
        self._current_timer = None
        self._timer_loop.cancel()
        self._timer_loop.start()
        self._is_started = True
        logger.info("Scheduler restart complete.")

    def stop(self) -> None:
        """
        Stop the scheduler.
        """
        self._is_started = False
        self._timer_loop.cancel()
        if self._current_task is not None:
            self._current_task.cancel()
        self._current_timer = None
        logger.info("Scheduler shutdown complete.")

    async def get_latest_timer(self, days: int = 7) -> DatabaseTimer | None:
        """Gets the latest timer in the specified range of days.

        Parameters
        ----------
        days : int, optional
            The maximum expiry of the timer, by default 5

        Returns
        -------
        Optional[Timer]
            The timer object that was found, if any.
        """
        await self.app.wait_until_started()
        model = await DatabaseTimer.filter(Q(expires__lte=utcnow() + datetime.timedelta(days=days))).first()
        return model

    async def _call_timer(self, timer: DatabaseTimer) -> None:
        """Calls the provided timer, dispatches TimerCompleteEvent, and removes the timer object from
        the database.

        Parameters
        ----------
        timer : BaseTimerEvent
            The timer to be called.
        """

        await timer.delete()
        self._current_timer = None
        try:
            self_timer: typing.Type[BaseTimerEvent] = timers_dict_enum_to_class[timer.event]
            event = self_timer(self.app, timer.guild_id, timer)

            self.app.dispatch(event)
            logger.info(f"Dispatched timer {event.__class__} (ID: {event.timer.id})")
        except Exception as error:
            exception_msg = "\n".join(traceback.format_exception(type(error), error, error.__traceback__))
            logger.error(exception_msg)

    async def _dispatch_timers(self):
        """
        A task that loops, waits for, and calls pending timers.
        """
        try:
            while self.app.is_ready and self._is_started:
                timer = await self.get_latest_timer(days=30)
                self._current_timer = timer

                now = utcnow()

                if not timer:
                    break

                if timer.expires >= now:
                    sleep_time = (timer.expires - now).total_seconds()
                    logger.info("Awaiting next timer: '{}' (ID: {}), which is in {}s",
                                timer.event,
                                timer.id,
                                sleep_time)

                    await asyncio.sleep(sleep_time)

                # TODO: Maybe some sort of queue system so we do not spam out timers like crazy after restart?
                logger.info(f"Dispatching timer: {timer.event.name} (ID: {timer.id})")
                await self._call_timer(timer)

        except asyncio.CancelledError:
            raise

        except (OSError, hikari.GatewayServerClosedConnectionError):
            if self._current_task:
                self._current_task.cancel()

            self._current_task = asyncio.create_task(self._dispatch_timers())

    async def _wait_for_active_timers(self) -> None:
        """
        Check every hour to see if new timers meet criteria in the database.
        """
        if self._current_task is None:
            self._current_task = asyncio.create_task(self._dispatch_timers())

    async def get_timer(self, timer_id: int) -> DatabaseTimer:
        """Retrieve a currently pending timer.

        Parameters
        ----------
        timer_id : int
            The ID of the timer object.

        Returns
        -------
        Timer
            The located timer object.

        Raises
        ------
        ValueError
            The timer was not found.
        """

        model = await DatabaseTimer.filter(id=timer_id).first()

        if model is None:
            raise ValueError("Invalid timer_id: Timer not found.")

        return model

    async def create_timer(
            self,
            expires: datetime.datetime,
            event: TimerEnum,
            guild: hikari.SnowflakeishOr[hikari.PartialGuild],
            user: hikari.SnowflakeishOr[hikari.PartialUser],
            channel: hikari.SnowflakeishOr[hikari.TextableChannel] | None = None,
            *,
            extra: dict | None = None,
    ) -> DatabaseTimer:
        """Create a new timer and schedule it.

        Parameters
        ----------
        expires : datetime.datetime
            The expiry date of the timer. Must be in the future.
        event : TimerEvent
            The event string to identify this timer by.
        guild : hikari.SnowflakeishOr[hikari.PartialGuild]
            The guild this timer belongs to.
        user : hikari.SnowflakeishOr[hikari.PartialUser]
            The user this timer belongs to.
        channel : t.Optional[hikari.SnowflakeishOr[hikari.TextableChannel]], optional
            The channel to bind this timer to, by default None
        extra : t.Optional[str], optional
            Optional parameters or data to include, by default None

        Returns
        -------
        Timer
            The timer object that got created.
        """
        if not self._is_started:
            raise hikari.ComponentStateConflictError("The scheduler is not running.")
        model = await DatabaseTimer.create(guild_id=guild,
                                           user_id=user,
                                           channel_id=channel,
                                           event=event,
                                           expires=expires.astimezone(datetime.timezone.utc),
                                           created=utcnow(),
                                           extra=extra)

        # If there is already a timer in queue, and it has an expiry that is further than the timer we just created
        # then we restart the dispatch_timers() to re-check for the latest timer.
        if self._current_timer and model.expires < self._current_timer.expires:
            logger.debug("Reshuffled timers, created timer is now the latest timer.")
            if self._current_task:
                self._current_task.cancel()
            self._current_task = asyncio.create_task(self._dispatch_timers())

        elif self._current_timer is None:
            self._current_task = asyncio.create_task(self._dispatch_timers())

        return model

    async def update_timer(self, timer: DatabaseTimer) -> None:
        """Update a currently running timer, replacing it with the specified timer object.
        If needed, reshuffles timers.

        Parameters
        ----------
        timer : Timer
            The timer object to update.
        """
        await timer.save()

        if self._current_timer and timer.expires < self._current_timer.expires:
            logger.debug("Reshuffled timers, created timer is now the latest timer.")
            if self._current_timer and timer.expires <= self._current_timer.expires:
                if self._current_task:
                    self._current_task.cancel()
                self._current_task = asyncio.create_task(self._dispatch_timers())

    async def cancel_timer(self, timer_id: int) -> DatabaseTimer | None:
        """Prematurely cancel a timer before expiry. Returns the cancelled timer.

        Parameters
        ----------
        timer_id : int
            The ID of the timer to be cancelled.

        Returns
        -------
        Timer
            The cancelled timer object.
        """
        model = await self.get_timer(timer_id)

        if model is None:
            return None
        copied = copy.deepcopy(model)
        await model.delete()

        if self._current_timer and self._current_timer.id == model.id:
            if self._current_task:
                self._current_task.cancel()
            self._current_task = asyncio.create_task(self._dispatch_timers())

        return copied

    async def convert_time(
            self,
            time_str: str,
            *,
            user: hikari.SnowflakeishOr[hikari.PartialUser] | None = None,
            conversion_mode: ConversionMode | None = None,
            future_time: bool = False,
    ) -> datetime.datetime:
        """Try converting a string of human-readable time to a datetime object.

        Raises
        ------
        ValueError
            Time could not be parsed using relative conversion.
        ValueError
            Time could not be parsed using absolute conversion.
        ValueError
            Time is not in the future.
        """
        user_id = hikari.Snowflake(user) if user else None
        logger.debug(f"String passed for time conversion: {time_str}")

        if not conversion_mode or conversion_mode == ConversionMode.RELATIVE:
            # Relative time conversion Get any pair of <number><word> with a single optional space in between,
            # and return them as a dict (sort of)
            time_regex = re.compile(r"(\d+(?:[.,]\d+)?)\s?(\w+)")
            time_letter_dict = {
                "h": 3600,
                "s": 1,
                "m": 60,
                "d": 86400,
                "w": 86400 * 7,
                "M": 86400 * 30,
                "Y": 86400 * 365,
                "y": 86400 * 365,
            }
            time_word_dict = {
                "hour": 3600,
                "second": 1,
                "minute": 60,
                "day": 86400,
                "week": 86400 * 7,
                "month": 86400 * 30,
                "year": 86400 * 365,
                "sec": 1,
                "min": 60,
            }
            matches = time_regex.findall(time_str)
            time = 0.0

            for input_str, category in matches:
                input_str = input_str.replace(",",
                                              ".")  # Replace commas with periods to correctly register decimal places
                # If this is a single letter

                if len(category) == 1:
                    if value := time_letter_dict.get(category):
                        time += value * float(input_str)

                else:
                    for string, value in time_word_dict.items():
                        if (
                                category.lower() == string or category.lower()[:-1] == string
                        ):  # Account for plural forms of the word
                            time += value * float(input_str)
                            break

            if time > 0:  # If we found time
                return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=time)

            if conversion_mode == ConversionMode.RELATIVE:
                raise ValueError("Failed time conversion. (relative)")

        if not conversion_mode or conversion_mode == ConversionMode.ABSOLUTE:

            timezone = "UTC"
            if user_id:
                model = await DatabaseUser.fetch(user_id)
                timezone = model.tz

            time_parsed = dateparser.parse(
                time_str, settings={"RETURN_AS_TIMEZONE_AWARE": True, "TIMEZONE": timezone, "NORMALIZE": True}
            )

            if not time_parsed:
                raise ValueError("Time could not be parsed. (absolute)")

            if future_time and time_parsed < datetime.datetime.now(datetime.timezone.utc):
                raise ValueError("Time is not in the future!")

            return time_parsed

        raise ValueError("Time conversion failed.")


SchedulerService = SchedulerServiceT()


def load(bot: "Airy"):
    bot.subscribe(hikari.StartedEvent, SchedulerService.setup)


def unload(_: "Airy"):
    SchedulerService.stop()
