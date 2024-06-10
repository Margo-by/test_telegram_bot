import asyncio

from logging.config import fileConfig
from sqlalchemy.ext.asyncio import create_async_engine, AsyncAdaptedPool

from alembic import context
from models import Base

# Объект конфигурации Alembic, который предоставляет доступ к значениям в используемом .ini файле.
config = context.config

# Настраиваем логирование Python в соответствии с конфигурацией Alembic.
fileConfig(config.config_file_name)

# Определяем переменную target_metadata, которая содержит метаданные для миграций.
target_metadata = Base.metadata

# Функция для выполнения миграций в оффлайн-режиме.
def run_migrations_offline():
    # Получаем URL для подключения к базе данных из конфигурации.
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    # Запускаем миграции в транзакции.
    with context.begin_transaction():
        context.run_migrations()

# Функция для выполнения миграций в онлайн-режиме.
async def run_migrations_online():
    # Создаем подключаемый объект к базе данных, используя настройки из конфигурации.
    connectable = create_async_engine(config.get_main_option("sqlalchemy.url"), echo=True, future=True, poolclass=AsyncAdaptedPool)

    # Устанавливаем соединение с базой данных.
    async with connectable.connect() as connection:
        # Настраиваем контекст миграций для онлайн-режима.
        await do_run_migrations(connection)

async def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)

    # Запускаем миграции в транзакции.
    with context.begin_transaction():
        context.run_migrations()

# Определяем, в каком режиме работают миграции: оффлайн или онлайн, и вызываем соответствующую функцию.
if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
