import asyncio
import signal
from loggate import getLogger, setup_logging

from config import get_config, log_level
from lib.db import DBConnection
from lib.helper import dicts_val, get_yaml
from model.server import WGServer

SERVER_NAME = get_config('SERVER_NAME')
graceful_signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)

logging_profiles = get_yaml(get_config('LOGGING_DEFINITIONS'))
if get_config('LOG_LEVEL'):
    root_profile = dicts_val('profiles.default.loggers.root', logging_profiles)
    root_profile['level'] = get_config('LOG_LEVEL', wrapper=log_level)
setup_logging(profiles=logging_profiles)

logger = getLogger('main')
wg_server = WGServer(SERVER_NAME)


async def graceful_shutdown(loop, sig=None):
    """Cleanup tasks tied to the service's shutdown."""
    if sig:
        logger.info(f"Received exit signal {sig.name}...")
    tasks = [t for t in asyncio.all_tasks() if t is not
             asyncio.current_task()]
    [task.cancel() for task in tasks]
    logger.info(f"Cancelling {len(tasks)} outstanding tasks")
    await asyncio.gather(*tasks, return_exceptions=True)
    loop.stop()


def handle_exception(loop, context):
    msg = context.get("exception", context["message"])
    logger.error(f"Caught exception: {msg}")
    logger.info("Shutting down...")
    asyncio.create_task(graceful_shutdown(loop))


def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.set_exception_handler(handle_exception)
    for sig in graceful_signals:
        loop.add_signal_handler(
            sig, lambda s=sig: asyncio.create_task(graceful_shutdown(loop, s)))
    conn = DBConnection()
    loop.run_until_complete(conn.start())
    try:
        loop.run_until_complete(wg_server.start_server(conn))
        loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        logger.info("The gpio is graceful shutdown.")
    finally:
        loop.run_until_complete(wg_server.stop_server(conn))
        loop.run_until_complete(conn.stop())


if __name__ == "__main__":
    main()
