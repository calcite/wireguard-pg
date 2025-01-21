from asyncpg import Pool
import loggate
from fastapi import APIRouter, Depends, Form, HTTPException

from model.user import JWT, UserDB, LoginRequest
from lib.db import db_pool, db_logger

router = APIRouter(tags=["user"])
sql_logger = 'sql.user'
logger = loggate.getLogger('user')


@router.post("/login", response_model=JWT)
async def do_login(login_req: LoginRequest = Form(), pool: Pool = Depends(db_pool)):
    try:
        async with pool.acquire() as db, db_logger(sql_logger, db):
            if user := await UserDB.login(db, login_req):
                return user
    except Exception as ex:
        logger.error(ex, exc_info=ex)
    raise HTTPException(
        status_code=401,
        detail="Invalid username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )
