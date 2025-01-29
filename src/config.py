import logging
import os
import re
from typing import Callable

BASE_DIR = f'{os.path.dirname(os.path.realpath(__file__))}/'

DEFAULT_CONFIG = {
    'SERVER_NAME': 'default',
    'DATABASE_URI': 'postgres://user:password@localhost:5432/db',
    'DATABASE_INIT': 'yes',
    'DATABASE_INTERFACE_TABLE_NAME': 'interface',
    'DATABASE_PEER_TABLE_NAME': 'peer',
    'POSTGRES_POOL_MIN_SIZE': 5,
    'POSTGRES_POOL_MAX_SIZE': 10,
    'POSTGRES_CONNECTION_TIMEOUT': 5,
    'POSTGRES_CONNECTION_CHECK': 5,
    'LOGGING_DEFINITIONS': f'{BASE_DIR}logging.yml',
    'MIGRATION_DIR': 'migration/',
    'CORS_ALLOW_ORIGINS': '*',  # comma separated
    'CORS_ALLOW_METHODS': '*',  # comma separated
    'CORS_ALLOW_HEADERS': '*',  # comma separated
    'CORS_ALLOW_CREDENTIALS': 'yes',
    'WIREGUARD_CONFIG_FOLDER': '/config',
    'API_ENABLED': 'no',
    'LOG_LEVEL': 'INFO',
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


_logname_to_level = {
    'CRITICAL': logging.CRITICAL,
    'FATAL': logging.FATAL,
    'ERROR': logging.ERROR,
    'WARN': logging.WARNING,
    'WARNING': logging.WARNING,
    'INFO': logging.INFO,
    'DEBUG': logging.DEBUG,
    'NOTSET': logging.NOTSET,
}


def log_level(name):
    if isinstance(name, int):
        return name
    return _logname_to_level.get(name.upper(), logging.INFO)
