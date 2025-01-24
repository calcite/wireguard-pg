from asyncpg import Pool
import loggate
from fastapi import APIRouter, Depends, Security, HTTPException, status

from model.user import User, get_user
from model.interface import InterfaceDB, Interface, InterfaceUpdate, InterfaceCreate
from lib.db import db_pool, db_logger

router = APIRouter(tags=["interface"])
sql_logger = 'sql.interface'
logger = loggate.getLogger('Interface')


@router.get("/{Interface_id}", response_model=Interface)
async def get_file(Interface_id: int,
                   pool: Pool = Depends(db_pool),
                   user: User = Security(get_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    async with pool.acquire() as db, db_logger(sql_logger, db):
        return await InterfaceDB.get(db, Interface_id)


@router.put("/{Interface_id}", response_model=Interface)
async def file_update(Interface_id: int,
                      update: InterfaceUpdate,
                      pool: Pool = Depends(db_pool),
                      user: User = Security(get_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    async with pool.acquire() as db, db.transaction(), db_logger(sql_logger, db):
        return await InterfaceDB.update(db, Interface_id, update)


@router.delete("/{Interface_id}", status_code=status.HTTP_204_NO_CONTENT)
async def file_delete(Interface_id: int,
                      pool: Pool = Depends(db_pool),
                      user: User = Security(get_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    async with pool.acquire() as db, db.transaction(), db_logger(sql_logger, db):
        await InterfaceDB.delete(db, Interface_id)


@router.post("/", response_model=Interface,
             status_code=status.HTTP_201_CREATED)
async def usergroup_create(create: InterfaceCreate,
                           pool: Pool = Depends(db_pool),
                           user: User = Security(get_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    async with pool.acquire() as db, db.transaction(), db_logger(sql_logger, db):
        return await InterfaceDB.create(db, create)
