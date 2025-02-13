from typing import List
import loggate
from fastapi import APIRouter, Depends, Security, status
from pydantic import BaseModel

from endpoints import check_token, get_token
from model.interface import InterfaceDB, Interface, InterfaceUpdate, InterfaceCreate
from lib.db import db_pool, DBPool

router = APIRouter(tags=["interface"])
sql_logger = 'sql.interface'
logger = loggate.getLogger('Interface')


@router.get("/", response_model=List[Interface])
async def gets(pool: DBPool = Depends(db_pool),
               token: bool = Security(get_token)):
    check_token(token)
    async with pool.acquire_with_log(sql_logger) as db:
        return await InterfaceDB.gets(db)


@router.get("/{interface_id}", response_model=Interface)
async def get(interface_id: int,
              pool: DBPool = Depends(db_pool),
              token: bool = Security(get_token)):
    check_token(token)
    async with pool.acquire_with_log(sql_logger) as db:
        return await InterfaceDB.get(db, interface_id)


@router.put("/{interface_id}", response_model=Interface)
async def update(interface_id: int,
                 update: InterfaceUpdate,
                 pool: DBPool = Depends(db_pool),
                 token: bool = Security(get_token)):
    check_token(token)
    async with pool.acquire_with_log(sql_logger) as db, db.transaction():
        return await InterfaceDB.update(db, interface_id, update)


@router.delete("/{interface_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(interface_id: int,
                 pool: DBPool = Depends(db_pool),
                 token: bool = Security(get_token)):
    check_token(token)
    async with pool.acquire_with_log(sql_logger) as db, db.transaction():
        await InterfaceDB.delete(db, interface_id)


@router.post("/", response_model=Interface,
             status_code=status.HTTP_201_CREATED)
async def create(create: InterfaceCreate,
                 pool: DBPool = Depends(db_pool),
                 token: bool = Security(get_token)):
    check_token(token)
    async with pool.acquire_with_log(sql_logger) as db, db.transaction():
        return await InterfaceDB.create(db, create)


class FreeIp(BaseModel):
    ip: str

@router.get("/{interface_id}/free_ip", response_model=FreeIp)
async def get_free_ip(interface_id: int,
                      pool: DBPool = Depends(db_pool),
                      token: bool = Security(get_token)):
    check_token(token)
    async with pool.acquire_with_log(sql_logger) as db:
        iface = await InterfaceDB.get(db, interface_id)
        return FreeIp(
            ip=str((await InterfaceDB.get_free_ips(db, iface)).pop(0))
        )