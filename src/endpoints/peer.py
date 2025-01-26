from typing import List
from asyncpg import Pool
import loggate
from fastapi import APIRouter, Depends, Security, HTTPException, status

from model.user import User, get_user
from model.peer import PeerDB, Peer, PeerUpdate, PeerCreate
from lib.db import db_pool, db_logger

router = APIRouter(tags=["peer"])
sql_logger = 'sql.peer'
logger = loggate.getLogger('Peer')


@router.get("/", response_model=List[Peer])
async def get_file(pool: Pool = Depends(db_pool),
                   user: User = Security(get_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    async with pool.acquire() as db, db_logger(sql_logger, db):
        return await PeerDB.gets(db)

@router.get("/{peer_id}", response_model=Peer)
async def get_file(peer_id: int,
                   pool: Pool = Depends(db_pool),
                   user: User = Security(get_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    async with pool.acquire() as db, db_logger(sql_logger, db):
        return await PeerDB.get(db, peer_id)


@router.put("/{peer_id}", response_model=Peer)
async def file_update(peer_id: int,
                      update: PeerUpdate,
                      pool: Pool = Depends(db_pool),
                      user: User = Security(get_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    async with pool.acquire() as db, db.transaction(), db_logger(sql_logger, db):
        return await PeerDB.update(db, peer_id, update)


@router.delete("/{peer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def file_delete(peer_id: int,
                      pool: Pool = Depends(db_pool),
                      user: User = Security(get_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    async with pool.acquire() as db, db.transaction(), db_logger(sql_logger, db):
        await PeerDB.delete(db, peer_id)


@router.post("/", response_model=Peer,
             status_code=status.HTTP_201_CREATED)
async def create(create: PeerCreate,
                 pool: Pool = Depends(db_pool),
                 user: User = Security(get_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    async with pool.acquire() as db, db.transaction(), db_logger(sql_logger, db):
        return await PeerDB.create(db, create)
