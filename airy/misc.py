import sentry_sdk
from loguru import logger

from airy.models.bot import Airy

bot = Airy()
# i18n = I18nMiddleware("bot", locales_dir, default="en")

if True:
    logger.info("Setup Sentry SDK")
    sentry_sdk.init(
        "https://afcb247293e24d7ab155ec3dcd94f318@o4504128802652160.ingest.sentry.io/4504567669260288",
        traces_sample_rate=1.0,
    )


def setup():
    bot.run()

