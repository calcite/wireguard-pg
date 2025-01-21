
from fastapi import FastAPI, Response
from fastapi.concurrency import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from loggate import getLogger, setup_logging

from config import get_config, to_bool
from lib.db import db_pool
from lib.helper import get_yaml


logging_profiles = get_yaml(get_config('LOGGING_DEFINITIONS'))
setup_logging(profiles=logging_profiles)

logger = getLogger('main')


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = await db_pool()
    try:
        yield
    finally:
        await pool.close()
        logger.info('Database connection pool closed')

app = FastAPI(debug=get_config('DEBUG', False, wrapper=bool), root_path='', lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_config('CORS_ALLOW_ORIGINS').split(','),
    allow_credentials=get_config('CORS_ALLOW_CREDENTIALS', wrapper=to_bool),
    allow_methods=get_config('CORS_ALLOW_METHODS').split(','),
    allow_headers=get_config('CORS_ALLOW_HEADERS').split(','),
)

from endpoints.user import router as user_router        # noqa
from endpoints.link import router as link_router        # noqa
app.include_router(user_router, prefix="/api/user")
app.include_router(link_router, prefix="/api/link")
# app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def root():
    return Response('Hello')
