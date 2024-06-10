import asyncio
import logging
import asyncpg

from sqlalchemy.ext.asyncio import create_async_engine

from models import Base
from config import settings

DATABASE_URL = settings.DATABASE_URL

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def init_db():
    logger.info("Инициализация базы данных...")
    engine = create_async_engine(DATABASE_URL, echo=True, future=True, pool_pre_ping=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("База данных инициализирована успешно.")


if __name__ == "__main__":
    asyncio.run(init_db())
