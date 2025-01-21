from asyncpg import Pool
import loggate
from fastapi import APIRouter, Depends, Security, HTTPException, status

from model.user import User, get_user
from model.link import LinkDB, Link, LinkUpdate, LinkCreate
from lib.db import db_pool, db_logger

router = APIRouter(tags=["file_thumb"])
sql_logger = 'sql.public'
logger = loggate.getLogger('Link')


@router.get("/{link_id}", response_model=Link)
async def get_file(link_id: int,
                   pool: Pool = Depends(db_pool),
                   user: User = Security(get_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    async with pool.acquire() as db, db_logger(sql_logger, db):
        return await LinkDB.get(db, link_id)


@router.put("/{link_id}", response_model=Link)
async def file_update(link_id: int,
                      update: LinkUpdate,
                      pool: Pool = Depends(db_pool),
                      user: User = Security(get_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    async with pool.acquire() as db, db.transaction(), db_logger(sql_logger, db):
        return await LinkDB.update(db, link_id, update)


@router.delete("/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def file_delete(link_id: int,
                      pool: Pool = Depends(db_pool),
                      user: User = Security(get_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    async with pool.acquire() as db, db.transaction(), db_logger(sql_logger, db):
        await LinkDB.delete(db, link_id)


@router.post("/", response_model=Link,
             status_code=status.HTTP_201_CREATED)
async def usergroup_create(create: LinkCreate,
                           pool: Pool = Depends(db_pool),
                           user: User = Security(get_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    async with pool.acquire() as db, db.transaction(), db_logger(sql_logger, db):
        return await LinkDB.create(db, create)
