from typing import List
from asyncpg import Pool
import loggate
from fastapi import APIRouter, Depends, Security, status

from endpoints import check_token
from model.interface import InterfaceDB, Interface, InterfaceUpdate, InterfaceCreate
from lib.db import db_pool, db_logger

router = APIRouter(tags=["interface"])
sql_logger = 'sql.interface'
logger = loggate.getLogger('Interface')


@router.get("/", response_model=List[Interface])
async def gets(pool: Pool = Depends(db_pool),
               checked: bool = Security(check_token)):
    async with pool.acquire() as db, db_logger(sql_logger, db):
        return await InterfaceDB.gets(db)


@router.get("/{Interface_id}", response_model=Interface)
async def get(Interface_id: int,
              pool: Pool = Depends(db_pool),
              checked: bool = Security(check_token)):
    async with pool.acquire() as db, db_logger(sql_logger, db):
        return await InterfaceDB.get(db, Interface_id)


@router.put("/{Interface_id}", response_model=Interface)
async def update(Interface_id: int,
                 update: InterfaceUpdate,
                 pool: Pool = Depends(db_pool),
                 checked: bool = Security(check_token)):
    async with pool.acquire() as db, db.transaction(), db_logger(sql_logger, db):
        return await InterfaceDB.update(db, Interface_id, update)


@router.delete("/{Interface_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(Interface_id: int,
                 pool: Pool = Depends(db_pool),
                 checked: bool = Security(check_token)):
    async with pool.acquire() as db, db.transaction(), db_logger(sql_logger, db):
        await InterfaceDB.delete(db, Interface_id)


@router.post("/", response_model=Interface,
             status_code=status.HTTP_201_CREATED)
async def create(create: InterfaceCreate,
                 pool: Pool = Depends(db_pool),
                 checked: bool = Security(check_token)):
    async with pool.acquire() as db, db.transaction(), db_logger(sql_logger, db):
        return await InterfaceDB.create(db, create)
