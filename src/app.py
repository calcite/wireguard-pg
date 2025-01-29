from fastapi import FastAPI, Response
from fastapi.concurrency import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from loggate import getLogger, setup_logging

from config import get_config, log_level, to_bool
from lib.db import DBConnection
from lib.helper import dicts_val, get_yaml
from model.server import WGServer

SERVER_NAME = get_config('SERVER_NAME')

logging_profiles = get_yaml(get_config('LOGGING_DEFINITIONS'))
if get_config('LOG_LEVEL'):
    root_profile = dicts_val('profiles.default.loggers.root', logging_profiles)
    root_profile['level'] = get_config('LOG_LEVEL', wrapper=log_level)
setup_logging(profiles=logging_profiles)

logger = getLogger('main')
wg_server = WGServer(SERVER_NAME)


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = DBConnection()
    await conn.start()
    try:
        await wg_server.start_server(conn)
        yield
    finally:
        await wg_server.stop_server(conn)
        await conn.stop()


app = FastAPI(debug=get_config('DEBUG', False, wrapper=bool), root_path='', lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_config('CORS_ALLOW_ORIGINS').split(','),
    allow_credentials=get_config('CORS_ALLOW_CREDENTIALS', wrapper=to_bool),
    allow_methods=get_config('CORS_ALLOW_METHODS').split(','),
    allow_headers=get_config('CORS_ALLOW_HEADERS').split(','),
)

if get_config('API_ENABLED', wrapper=to_bool):
    if not get_config('API_ACCESS_TOKEN'):
        logger.warning('You have not setup API_ACCESS_TOKEN. Whole API is '
                       'accessible for everyone. This is only for debug.')
    from endpoints.interface import router as interface_router        # noqa
    app.include_router(interface_router, prefix="/api/interface")
    from endpoints.peer import router as peer_router        # noqa
    app.include_router(peer_router, prefix="/api/peer")


@app.get("/", include_in_schema=False)
async def root():
    return Response('Hello')
