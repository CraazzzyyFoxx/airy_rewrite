import typing as t

from pydantic import BaseSettings


class BotConfig(BaseSettings):
    token: str
    dev_guilds: t.List[int]
    dev_mode: bool
    errors_trace_channel: int
    info_channel: int
    stats_channel: int

    class Config:
        env_file = ".env"
        env_prefix = "bot_"


bot_config = BotConfig()
