from __future__ import annotations

import asyncio
import datetime
import re
import traceback
import typing
import typing as t

import dateparser  # type: ignore
import hikari

from hikari.internal.enums import Enum
from loguru import logger

from airy.models import DatabaseTimer, DatabaseUser, BaseTimerEvent, timers_dict_enum_to_class, TimerEnum
from airy.utils.tasks import IntervalLoop
from airy.utils.time import utcnow

if t.TYPE_CHECKING:
    from airy.models.bot import Airy

__all__ = ("ConversionMode",
           "SchedulerService")

BaseTimerEventT = t.TypeVar('BaseTimerEventT', bound=BaseTimerEvent)


class ConversionMode(int, Enum):
    """All possible time conversion modes."""

    RELATIVE = 0
    ABSOLUTE = 1


class SchedulerService:
    """
    All timer-related functionality, including time conversion from strings,
    creation, scheduling & dispatching of timers.
    Essentially the internal scheduler of the bot.
    """

    app: t.Optional[Airy] = None
    _is_started: bool = False
    _current_timer: t.Optional[DatabaseTimer] = None  # Currently, active timer that is being awaited
    _current_task: t.Optional[asyncio.Task] = None  # Current task that is handling current_timer
    _timer_loop: t.Optional[IntervalLoop] = None

    @classmethod
    def current_timer(cls):
        return cls._current_timer

    @classmethod
    async def setup(cls, event: hikari.StartedEvent):
        cls.start(event.app)  # type: ignore

    @classmethod
    def start(cls, app: "Airy") -> None:
        """
        Start the scheduler.
        """
        cls.app = app
        cls._timer_loop = IntervalLoop(cls._wait_for_active_timers, hours=1.0)
        cls._timer_loop.start()
        cls._is_started = True
        logger.info("Scheduler startup complete.")

    @classmethod
    def restart(cls) -> None:
        """
        Restart the scheduler.
        """
        cls._is_started = False
        if cls._current_task is not None:
            cls._current_task.cancel()
        cls._current_task = None
        cls._current_timer = None
        cls._timer_loop.cancel()
        cls._timer_loop.start()
        cls._is_started = True
        logger.info("Scheduler restart complete.")

    @classmethod
    def stop(cls) -> None:
        """
        Stop the scheduler.
        """
        cls._is_started = False
        cls._timer_loop.cancel()
        if cls._current_task is not None:
            cls._current_task.cancel()
        cls._current_timer = None
        logger.info("Scheduler shutdown complete.")

    @classmethod
    async def get_latest_timer(cls, days: int = 7) -> t.Optional[DatabaseTimer]:
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
        await cls.app.wait_until_started()
        model = await DatabaseTimer.fetch_first(days)
        return model

    @classmethod
    async def _call_timer(cls, timer: DatabaseTimer) -> None:
        """Calls the provided timer, dispatches TimerCompleteEvent, and removes the timer object from
        the database.

        Parameters
        ----------
        timer : BaseTimerEvent
            The timer to be called.
        """

        await timer.delete()
        cls._current_timer = None
        try:
            cls_timer: typing.Type[BaseTimerEvent] = timers_dict_enum_to_class[timer.event]
            event = cls_timer(cls.app, timer.guild_id, timer)

            cls.app.dispatch(event)
            logger.info(f"Dispatched timer {timer.__class__} (ID: {timer.id})")
        except Exception as error:
            exception_msg = "\n".join(traceback.format_exception(type(error), error, error.__traceback__))
            logger.error(exception_msg)

    @classmethod
    async def _dispatch_timers(cls):
        """
        A task that loops, waits for, and calls pending timers.
        """
        try:
            while cls.app.is_ready and cls._is_started:
                timer = await cls.get_latest_timer(days=30)
                cls._current_timer = timer

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
                await cls._call_timer(timer)

        except asyncio.CancelledError:
            raise

        except (OSError, hikari.GatewayServerClosedConnectionError):
            if cls._current_task:
                cls._current_task.cancel()

            cls._current_task = asyncio.create_task(cls._dispatch_timers())

    @classmethod
    async def _wait_for_active_timers(cls) -> None:
        """
        Check every hour to see if new timers meet criteria in the database.
        """
        if cls._current_task is None:
            cls._current_task = asyncio.create_task(cls._dispatch_timers())

    @classmethod
    async def get_timer(cls, timer_id: int) -> DatabaseTimer:
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

        model = await DatabaseTimer.fetch(timer_id=timer_id)

        if model is None:
            raise ValueError("Invalid timer_id: Timer not found.")

        return model

    @classmethod
    async def create_timer(
            cls,
            expires: datetime.datetime,
            event: TimerEnum,
            guild: hikari.SnowflakeishOr[hikari.PartialGuild],
            user: hikari.SnowflakeishOr[hikari.PartialUser],
            channel: t.Optional[hikari.SnowflakeishOr[hikari.TextableChannel]] = None,
            *,
            extra: t.Optional[dict] = None,
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
        if not cls._is_started:
            raise hikari.ComponentStateConflictError("The scheduler is not running.")
        model = await DatabaseTimer.create(guild=guild,
                                           user=user,
                                           channel=channel,
                                           event=event,
                                           expires=expires.astimezone(datetime.timezone.utc),
                                           created=utcnow(),
                                           extra=extra)

        # If there is already a timer in queue, and it has an expiry that is further than the timer we just created
        # then we restart the dispatch_timers() to re-check for the latest timer.
        if cls._current_timer and model.expires < cls._current_timer.expires:
            logger.debug("Reshuffled timers, created timer is now the latest timer.")
            if cls._current_task:
                cls._current_task.cancel()
            cls._current_task = asyncio.create_task(cls._dispatch_timers())

        elif cls._current_timer is None:
            cls._current_task = asyncio.create_task(cls._dispatch_timers())

        return model

    @classmethod
    async def update_timer(cls, timer: DatabaseTimer) -> None:
        """Update a currently running timer, replacing it with the specified timer object.
        If needed, reshuffles timers.

        Parameters
        ----------
        timer : Timer
            The timer object to update.
        """
        await timer.update()

        if cls._current_timer and timer.expires < cls._current_timer.expires:
            logger.debug("Reshuffled timers, created timer is now the latest timer.")
            if cls._current_timer and timer.expires <= cls._current_timer.expires:
                if cls._current_task:
                    cls._current_task.cancel()
                cls._current_task = asyncio.create_task(cls._dispatch_timers())

    @classmethod
    async def cancel_timer(cls, timer_id: int) -> t.Optional[DatabaseTimer]:
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
        model = await DatabaseTimer.fetch(timer_id=timer_id)

        if model is None:
            return None

        await model.delete()

        if cls._current_timer and cls._current_timer.id == model.id:
            if cls._current_task:
                cls._current_task.cancel()
            cls._current_task = asyncio.create_task(cls._dispatch_timers())

        return model

    @classmethod
    async def convert_time(
            cls,
            timestr: str,
            *,
            user: t.Optional[hikari.SnowflakeishOr[hikari.PartialUser]] = None,
            conversion_mode: t.Optional[ConversionMode] = None,
            future_time: bool = False,
    ) -> datetime.datetime:
        """Try converting a string of human-readable time to a datetime object.

        Parameters
        ----------
        timestr : str
            The string containing the time.
        user : t.Optional[hikari.SnowflakeishOr[hikari.PartialUser]], optional
            The user whose preferences will be used in the case of timezones, by default None
        force_mode : t.Optional[str], optional
            If specified, forces either 'relative' or 'absolute' conversion, by default None
        future_time : bool, optional
            If True and the time specified is in the past, raise an error, by default False

        Returns
        -------
        datetime.datetime
            The converted datetime.datetime object.

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
        logger.debug(f"String passed for time conversion: {timestr}")

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
            matches = time_regex.findall(timestr)
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
                timestr, settings={"RETURN_AS_TIMEZONE_AWARE": True, "TIMEZONE": timezone, "NORMALIZE": True}
            )

            if not time_parsed:
                raise ValueError("Time could not be parsed. (absolute)")

            if future_time and time_parsed < datetime.datetime.now(datetime.timezone.utc):
                raise ValueError("Time is not in the future!")

            return time_parsed

        raise ValueError("Time conversion failed.")


def load(bot: "Airy"):
    bot.subscribe(hikari.StartedEvent, SchedulerService.setup)


def unload(_: "Airy"):
    SchedulerService.stop()
