import logging
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


def setup_logger(level=logging.INFO,
                 log_file="log.log"):
    logger = logging.getLogger()
    logger.setLevel(level)
    log_path = Path(log_file).resolve()
    file_handler = next(
        (
            handler
            for handler in logger.handlers
            if isinstance(handler, logging.FileHandler)
            and Path(handler.baseFilename) == log_path
        ),
        None,
    )
    if file_handler is None:
        file_handler = logging.FileHandler(log_path)
        logger.addHandler(file_handler)

    file_handler.setLevel(level)
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(formatter)
    return logger


async def load_column_constraints(engine: AsyncEngine):
    query = text("""
        SELECT
            column_name,
            data_type,
            character_maximum_length,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = :table_name
    """)

    async with engine.connect() as conn:
        result = await conn.execute(
            query, {"table_name": "user_profiles"}
        )

        return {
            row.column_name: {
                "type": row.data_type,
                "max_length": row.character_maximum_length,
                "nullable": row.is_nullable == "YES",
                "default": row.column_default,
            }
            for row in result
        }