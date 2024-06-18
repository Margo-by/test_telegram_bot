import logging

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from models import UserValue
from config import settings

DATABASE_URL = settings.DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=True, future=True, pool_pre_ping=True)
AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

async def save_user_value(user_id: int, value: str):
    async with AsyncSessionLocal() as session:
        async with session.begin():
            try:
                # Удаляем все записи с аналогичным значением value для данного user_id
                await session.execute(
                    UserValue.__table__.delete().where(UserValue.user_id == user_id, UserValue.value == value)
                )
                logging.info(f"Удалены все записи для user_id: {user_id} с значением: {value}.")

                # Добавляем новое значение пользователя
                new_user_value = UserValue(user_id=user_id, value=value)
                session.add(new_user_value)
                await session.commit()
                logging.info(f"Значение {value} сохранено для user_id: {user_id}.")
            except Exception as e:
                logging.error(f"Ошибка при сохранении значения для user_id: {user_id}. Ошибка: {e}")
                await session.rollback()
                raise
