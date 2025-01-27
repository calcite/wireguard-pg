
import asyncio
from fastapi import FastAPI, Response
from fastapi.concurrency import asynccontextmanager
from fastapi.openapi.models import SecuritySchemeType
from fastapi.middleware.cors import CORSMiddleware
from loggate import getLogger, setup_logging

from config import get_config, log_level, to_bool
from lib.db import DBConnection
from lib.helper import dicts_val, get_yaml
from model.server import WGServer
from model.user import get_service_token

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
        # await wg_server.start_server(conn)
        yield
    finally:
        await conn.stop()


app = FastAPI(debug=get_config('DEBUG', False, wrapper=bool), root_path='', lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_config('CORS_ALLOW_ORIGINS').split(','),
    allow_credentials=get_config('CORS_ALLOW_CREDENTIALS', wrapper=to_bool),
    allow_methods=get_config('CORS_ALLOW_METHODS').split(','),
    allow_headers=get_config('CORS_ALLOW_HEADERS').split(','),
)

if get_config('ENABLE_API', wrapper=to_bool):
    token = get_service_token('service_token', 1)
    print('#'*150, f'\n\n  API token: {token}\n\n', '#'*150)

    from endpoints.interface import router as interface_router        # noqa
    app.include_router(interface_router, prefix="/api/interface")
    from endpoints.peer import router as peer_router        # noqa
    app.include_router(peer_router, prefix="/api/peer")
    # app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def root():
    return Response('Hello')
