import asyncio
from typing import Callable
import loggate
import re
from pathlib import Path
from packaging.version import Version
from asyncpg import connect, create_pool, Pool, Connection, UndefinedTableError
from asyncpg.connection import LoggedQuery

from config import get_config, to_bool

logger = loggate.getLogger('db')

DATABASE_URI = get_config('DATABASE_URI')
DATABASE_INIT = get_config('DATABASE_INIT', wrapper=to_bool)
MIGRATION_DIR = get_config('MIGRATION_DIR', wrapper=Path)
INTERFACE_TABLE = get_config('DATABASE_INTERFACE_TABLE_NAME')
POSTGRES_POOL_MIN_SIZE = get_config('POSTGRES_POOL_MIN_SIZE', wrapper=int)
POSTGRES_POOL_MAX_SIZE = get_config('POSTGRES_POOL_MAX_SIZE', wrapper=int)
POSTGRES_CONNECTION_TIMEOUT = get_config('POSTGRES_CONNECTION_TIMEOUT', wrapper=float)
POSTGRES_CONNECTION_CHECK = get_config('POSTGRES_CONNECTION_CHECK', wrapper=float)

pool = None
startup_callbacks = []
notification_callbacks = {}
checking_task = None


def db_startup(fce):
    global startup_callbacks
    startup_callbacks.append(fce)
    return fce


def register_notification(channel: str, fce: Callable):
    notification_callbacks[channel] = fce


async def __reg_notification_in_db(db: Connection):
    async def notify(_, pid, channel, payload):
        async with pool.acquire() as con:
            return await notification_callbacks[channel](con, channel, payload)
    for channel in notification_callbacks.keys():
        logger.info('Register %s listener.', channel)
        await db.add_listener(channel, notify)




def db_logger(logger_name: str, db: Connection):
    log = loggate.get_logger(logger_name)

    async def process(query: LoggedQuery):
        fce = log.error if query.exception else log.debug
        fce(query.query, meta={
            'args': query.args,
            'elapsed': query.elapsed,
        })

    class Log:
        async def __aenter__(self):
            db.add_query_logger(process)

        async def __aexit__(self, *exc):
            db.remove_query_logger(process)
    return Log()


async def update_db_schema(db_pool):
    res = INTERFACE_TABLE.split('.')
    table_schema = 'public'
    table_name = res.pop(0)
    if res:
        # table name contains schema as well
        table_schema = table_name
        table_name = res.pop(0)
    async with db_pool.acquire() as conn:
        try:
            count = await conn.fetchval('''
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = $1 AND table_name = $2
                ''',
                table_schema,
                table_name
            )
        except UndefinedTableError:
            count = 0
        if count > 0:
            return
        migs = list(MIGRATION_DIR.glob('update_*.sql'))
        migs.sort()
        for file in migs:
            logger.debug('Found db upgrade file %s', file)
            async with conn.transaction():
                with open(file, 'r') as f:
                    await conn.execute(f.read())
            logger.info('Create the database schema')

async def check_connection():
    global notification_callbacks, pool
    try:
        db: Connection = await connect(dsn=DATABASE_URI)
        await __reg_notification_in_db(db)
        while True:
            await asyncio.sleep(POSTGRES_CONNECTION_CHECK)
            await db.execute('select 1', timeout=POSTGRES_CONNECTION_TIMEOUT)
    except Exception as ex:
        logger.error("Connection was lost or not established", exc_info=ex)
    finally:
        await db.close()
        # pool.terminate()
        # pool = None

async def stop_pool():
    global checking_task, pool
    if checking_task:
        checking_task.cancel()
    if pool:
        try:
            await asyncio.wait_for(pool.close(), 3)
        except asyncio.TimeoutError:
            pool.terminate()
        pool = None
    logger.info('Database connection pool closed')

async def db_pool() -> Pool:
    global pool, startup_callbacks, checking_task
    if not pool:
        pool = await create_pool(
            dsn=DATABASE_URI,
            min_size=POSTGRES_POOL_MIN_SIZE,
            max_size=POSTGRES_POOL_MAX_SIZE,
        )
        logger.info(
            'Database connection pool initialized. URI: %s',
            re.sub(r':.*@', ':****@', DATABASE_URI)
        )
        if DATABASE_INIT:
            await update_db_schema(pool)
        if startup_callbacks:
            async with pool.acquire() as db:
                for fce in startup_callbacks:
                    await fce(db)
        if checking_task:
            checking_task.cancel()
        checking_task = asyncio.create_task(
            check_connection(),
            name='db-check'
        )
    return pool
