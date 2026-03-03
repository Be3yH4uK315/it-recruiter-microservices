import asyncio
import logging
from logging.handlers import RotatingFileHandler
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from app.core.config import settings
from app.core.resources import resources
from app.handlers import candidate, common, employer
from app.middlewares.logging import LoggingMiddleware, CustomFormatter
from app.middlewares.fsm_timeout import FSMTimeoutMiddleware


def setup_logging() -> None:
    """Настройка логирования."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_file = os.getenv("LOG_FILE", "bot.log")

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    file_handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=5
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(
        CustomFormatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(user_id)s - %(message)s"
        )
    )

    logging.getLogger().addHandler(file_handler)


async def main():
    """Главная функция запуска бота."""
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("Starting bot...")

    await resources.startup()

    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN, parse_mode="HTML")

    redis = Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT)
    storage = RedisStorage(redis=redis)

    dp = Dispatcher(storage=storage)

    dp.update.middleware(FSMTimeoutMiddleware())
    dp.message.outer_middleware(LoggingMiddleware())
    dp.callback_query.outer_middleware(LoggingMiddleware())

    dp.include_router(common.router)
    dp.include_router(candidate.router)
    dp.include_router(employer.router)

    try:
        logger.info("Bot polling started...")
        await dp.start_polling(bot)
    except Exception as e:
        logger.critical(f"Critical error starting bot: {e}", exc_info=True)
    finally:
        logger.info("Shutting down bot...")
        await resources.shutdown()
        await bot.session.close()
        await redis.aclose()
        logger.info("Bot shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped gracefully")
    except Exception as e:
        logging.critical(f"Unexpected error in main: {e}", exc_info=True)
