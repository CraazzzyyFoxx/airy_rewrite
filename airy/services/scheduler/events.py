import typing

import attr
import hikari

from airy.models.bot import Airy
from airy.models.events import AiryGuildEvent
from airy.services.scheduler.models import DatabaseTimer, TimerEnum
from airy.utils import format_relative, utcnow


@attr.define()
class BaseTimerEvent(AiryGuildEvent):
    app: Airy
    _guild_id: hikari.Snowflakeish
    timer: DatabaseTimer

    @property
    def human_delta(self):
        return format_relative(self.timer.created)

    @property
    def delta(self) -> typing.Union[float, int]:
        return (self.timer.expires - utcnow()).total_seconds()


@attr.define()
class ReminderEvent(BaseTimerEvent):
    app: Airy
    _guild_id: hikari.Snowflakeish
    timer: DatabaseTimer


timers_dict_enum_to_class = {TimerEnum.REMINDER: ReminderEvent}