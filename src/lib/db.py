import asyncio
from typing import Callable
import loggate
import re
from asyncpg.connection import Connection
from asyncpg.protocol import Record
from asyncpg.pool import PoolAcquireContext
from pathlib import Path
from asyncpg import connect, Pool, Connection, UndefinedTableError
from asyncpg.connection import LoggedQuery


from config import get_config, to_bool

logger = loggate.getLogger('db')

DATABASE_URI = get_config('DATABASE_URI')
DATABASE_INIT = get_config('DATABASE_INIT', wrapper=to_bool)
MIGRATION_DIR = get_config('MIGRATION_DIR', wrapper=Path)
POSTGRES_POOL_MIN_SIZE = get_config('POSTGRES_POOL_MIN_SIZE', wrapper=int)
POSTGRES_POOL_MAX_SIZE = get_config('POSTGRES_POOL_MAX_SIZE', wrapper=int)
POSTGRES_CONNECTION_TIMEOUT = get_config('POSTGRES_CONNECTION_TIMEOUT', wrapper=float)
POSTGRES_CONNECTION_CHECK = get_config('POSTGRES_CONNECTION_CHECK', wrapper=float)

class DBPoolAcquireContext(PoolAcquireContext):

    def __init__(self, pool, timeout, logger):
        self.logger = logger
        self.conn = None
        super().__init__(pool, timeout)

    async def process(self, query: LoggedQuery):
        fce = self.logger.error if query.exception else self.logger.debug
        fce(query.query, meta={
            'args': query.args,
            'elapsed': query.elapsed,
        })

    async def __aenter__(self) -> Connection:
        self.conn = await super().__aenter__()
        self.conn.add_query_logger(self.process)
        return self.conn

    async def __aexit__(self, *exc):
        if self.conn:
          self.conn.remove_query_logger(self.process)
        await super().__aexit__()


class DBPool(Pool):

  def acquire_with_log(self, logger, timeout=None) -> DBPoolAcquireContext:
    if isinstance(logger, str):
        logger = loggate.get_logger(logger)
    return DBPoolAcquireContext(self, timeout, logger)


class DBConnection:
    startup_callbacks = []
    notifications = {}
    singleton = None

    @classmethod
    async def get_pool(cls) -> Pool:
        if not cls.singleton:
            return None
        if not cls.singleton.pool:
            await cls.singleton.start_pool()
        return cls.singleton.pool

    @classmethod
    def register_startup(cls, fce: Callable):
        cls.startup_callbacks.append(fce)

    @classmethod
    def register_notification(cls, channel: str, fce: Callable):
        cls.notifications[channel] = fce

    @classmethod
    def db_logger(cls, logger_name: str, db: Connection):
        #  @Deprecated
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

    def __init__(self) -> None:
        self.end = False
        self.pool: Pool = None
        self.checking_task = None
        DBConnection.singleton = self

    async def update_db_schema(self):

        async with self.pool.acquire() as db:
            try:
                schema = 'public'
                if match := re.search(r'search_path=([^&\?]*)(&?|$)',
                                      DATABASE_URI, re.I):
                    schema = match.group(1)
                count = await db.fetchval(
                    '''
                        SELECT COUNT(*)
                        FROM information_schema.tables
                        WHERE table_schema = $1 AND table_name = $2
                    ''',
                    schema,
                    'server_interface'
                )
            except UndefinedTableError:
                count = 0
            if count > 0:
                return
            migs = list(MIGRATION_DIR.glob('update_*.sql'))
            migs.sort()
            for file in migs:
                logger.debug('Found db upgrade file %s', file)
                async with db.transaction():
                    with open(file, 'r') as f:
                        await db.execute(f.read())
                logger.info('Create the database schema')

    async def listener_handler(self, connection, pid, channel, payload):
        try:
            async with self.pool.acquire_with_log(f'{channel}.sql.listener') as db:
                return await self.notifications[channel](db, channel, payload)
        except Exception as ex:
            logger.error('Event handler failed: %s', ex, meta={
                "channel": channel,
                "payload": payload,
                "pid": pid
            }, exc_info=True)

    async def event_listener(self):
        db: Connection = None
        try:
            while not self.end:
                try:
                    logger.debug('Listener try to connect.')
                    db = await connect(
                        dsn=DATABASE_URI,
                        timeout=POSTGRES_CONNECTION_TIMEOUT
                    )
                    logger.info('Listener connected.')
                    for channel in self.notifications.keys():
                        logger.debug('Register %s listener.', channel)
                        await db.add_listener(channel, self.listener_handler)
                    while not db.is_closed() and not self.end:
                        await db.execute("SELECT 1", timeout=1)
                        await asyncio.sleep(30)
                except (TimeoutError, ConnectionRefusedError):
                    logger.debug('Listener connection timeout.')
                    await asyncio.sleep(30)
                except Exception as ex:
                    logger.error("Listener connection error", exc_info=ex)
                finally:
                    try:
                        if db:
                            await db.close(timeout=1)
                    except TimeoutError:
                        pass
        except Exception as ee:
            logger.error(ee)
        finally:
            logger.info('Listener is stopped.')

    async def start(self):
        await self.start_pool()
        if self.pool:
            if DATABASE_INIT:
                await self.update_db_schema()
            if self.startup_callbacks:
                async with self.pool.acquire() as db:
                    for fce in self.startup_callbacks:
                        await fce(db)
        if self.checking_task:
            self.checking_task.cancel()
        self.checking_task = asyncio.create_task(
            self.event_listener(),
            name='db-check'
        )

    async def stop(self):
        self.end = True
        # await asyncio.sleep(1)
        if self.checking_task:
            self.checking_task.cancel()
        await self.stop_pool()

    async def stop_pool(self):
        if self.pool:
            try:
                await asyncio.wait_for(self.pool.close(), 3)
            except asyncio.TimeoutError:
                self.pool.terminate()
            self.pool = None
        logger.info('Database connection pool closed')

    async def start_pool(self):
        if self.pool:
            await self.stop_pool()
        try:
            self.pool = await DBPool(
                DATABASE_URI,
                connection_class=Connection,
                record_class=Record,
                min_size=POSTGRES_POOL_MIN_SIZE,
                max_size=POSTGRES_POOL_MAX_SIZE,
                max_queries=50000,
                loop=None,
                connect=None,
                setup=None,
                init=None,
                reset=None,
                max_inactive_connection_lifetime=300.0,
            )
            # await create_pool(
            #     dsn=DATABASE_URI,
            #     min_size=POSTGRES_POOL_MIN_SIZE,
            #     max_size=POSTGRES_POOL_MAX_SIZE,
            #     timeout=POSTGRES_CONNECTION_TIMEOUT
            # )
            logger.info(
                'Database connection pool initialized. URI: %s',
                re.sub(r':.*@', ':****@', DATABASE_URI)
            )
        except (TimeoutError, ConnectionRefusedError):
            logger.warning('Database server is unavailable.')
            await asyncio.sleep(30)


async def db_pool() -> DBPool:
    return await DBConnection.get_pool()


def db_logger(logger_name: str, db: Connection):
    return DBConnection.db_logger(logger_name, db)