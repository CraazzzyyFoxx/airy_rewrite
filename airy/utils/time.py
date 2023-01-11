from datetime import datetime, timezone

from dateutil.relativedelta import relativedelta

from airy.utils.formats import format_dt
from airy.utils.formats import human_join, Plural



def utcnow() ->datetime:
    """A helper function to return an aware UTC datetime representing the current time.

    This should be preferred to :meth:`datetime.datetime.utcnow` since it is an aware
    datetime, compared to the naive datetime in the standard library.

    Returns
    --------
    :class:`datetime.datetime`
        The current aware datetime in UTC.
    """
    return datetime.now(timezone.utc)


def human_timedelta(dt, *, source=None, accuracy=3, brief=False, suffix=True):
    now = source or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    # Microsecond free zone
    now = now.replace(microsecond=0)
    dt = dt.replace(microsecond=0)

    # This implementation uses relative-delta instead of the much more obvious
    # div-mod approach with seconds because the seconds approach is not entirely
    # accurate once you go over 1 week in terms of accuracy since you have to
    # hardcode a month as 30 or 31 days.
    # A query like "11 months" can be interpreted as "!1 months and 6 days"
    if dt > now:
        delta = relativedelta(dt, now)
        suffix = ''
    else:
        delta = relativedelta(now, dt)
        suffix = ' ago' if suffix else ''

    attrs = [
        ('year', 'y'),
        ('month', 'mo'),
        ('day', 'd'),
        ('hour', 'h'),
        ('minute', 'm'),
        ('second', 's'),
    ]

    output = []
    for attr, brief_attr in attrs:
        elem = getattr(delta, attr + 's')
        if not elem:
            continue

        if attr == 'day':
            weeks = delta.weeks
            if weeks:
                elem -= weeks * 7
                if not brief:
                    output.append(format(Plural(weeks), 'week'))
                else:
                    output.append(f'{weeks}w')

        if elem <= 0:
            continue

        if brief:
            output.append(f'{elem}{brief_attr}')
        else:
            output.append(format(Plural(elem), attr))

    if accuracy is not None:
        output = output[:accuracy]

    if len(output) == 0:
        return 'now'
    else:
        if not brief:
            return human_join(output, final='and') + suffix
        else:
            return ' '.join(output) + suffix


def format_relative(dt):
    return format_dt(dt, 'R')


def format_date(dt):
    return format_dt(dt, 'f')
