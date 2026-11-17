import os
from pathlib import Path

from dotenv import dotenv_values

PROJECT_PATH = Path(__file__).parent.parent
ENV_PATH = PROJECT_PATH / ".env"
config_env = dotenv_values(ENV_PATH)

def get_config_value(var: str, default: str = None) -> str:
    return os.environ.get(var, default=config_env.get(var, default))

BOT_API = get_config_value("BOT_API")
ADMIN_CHATS_INFO = get_config_value("ADMIN_CHATS_INFO")
DB_USER = get_config_value("DB_USER")
DB_PASSWORD = get_config_value("DB_PASSWORD")
DB_HOST = get_config_value("DB_HOST")
DB_PORT = get_config_value("DB_PORT")
DB_NAME = get_config_value("DB_NAME")
ACHIEVEMENT_SERVICE_HOST = get_config_value("ACHIEVEMENT_SERVICE_HOST")
ENV = get_config_value("ENV")


# ADMIN_CHAT_ID = config_env.get("ADMIN_CHAT_ID")
# ADMIN_CHAT_ID = '..ADMIN_CHAT_ID'
