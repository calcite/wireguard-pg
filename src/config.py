import os
import re
from typing import Callable

BASE_DIR = f'{os.path.dirname(os.path.realpath(__file__))}/'

DEFAULT_CONFIG = {
    'JWT_SECRET': '<secret>',
    'JWT_ALGORITHM': 'HS256',
    'DATABASE_URI': 'postgres://user:password@localhost:5432/db',
    'POSTGRES_POOL_MIN_SIZE': 5,
    'POSTGRES_POOL_MAX_SIZE': 10,
    'LOGGING_DEFINITIONS': f'{BASE_DIR}logging.yml',
    'MIGRATION_DIR': 'migration/',
    'CORS_ALLOW_ORIGINS': '*',  # comma separated
    'CORS_ALLOW_METHODS': '*',  # comma separated
    'CORS_ALLOW_HEADERS': '*',  # comma separated
    'CORS_ALLOW_CREDENTIALS': 'yes',
}


def get_config(name: str, default=None, wrapper: Callable = None):
    if not wrapper:
        wrapper = lambda x: x  # NOQA
    return wrapper(os.getenv(name, DEFAULT_CONFIG.get(name, default)))


def apply_config(pattern: str):
    return re.sub(r'{([^}]+)}',
                  lambda matchobj: str(get_config(matchobj.group(1)) or ''),
                  pattern)


def to_bool(val) -> bool:
    return str(val).upper() in ['1', 'Y', 'YES', 'T', 'TRUE']
