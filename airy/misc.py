from pathlib import Path


from airy.models.bot import Airy

bot = Airy()
# i18n = I18nMiddleware("bot", locales_dir, default="en")

# if config.SENTRY_URL:
#     logger.info("Setup Sentry SDK")
#     sentry_sdk.init(
#         config.SENTRY_URL,
#         traces_sample_rate=1.0,
#     )


def setup():
    bot.run()

