from typing import List
import loggate
from fastapi import APIRouter, Depends, Security, status

from endpoints import check_token, get_token
from model.peer import PeerCreatePrivateKey, PeerCreated, PeerDB, Peer, PeerUpdate, PeerCreate
from lib.db import db_pool, DBPool

router = APIRouter(tags=["peer"])
sql_logger = 'sql.peer'
logger = loggate.getLogger('Peer')


@router.get("/", response_model=List[Peer])
async def gets(pool: DBPool = Depends(db_pool),
               token: bool = Security(get_token)):
    check_token(token)
    async with pool.acquire_with_log(sql_logger) as db:
        return await PeerDB.gets(db)


@router.get("/{peer_id}", response_model=Peer)
async def get(peer_id: int,
              pool: DBPool = Depends(db_pool),
              token: bool = Security(get_token)):
    check_token(token)
    async with pool.acquire_with_log(sql_logger) as db:
        return await PeerDB.get(db, peer_id)


@router.put("/{peer_id}", response_model=Peer)
async def update(peer_id: int,
                 update: PeerUpdate,
                 pool: DBPool = Depends(db_pool),
                 token: bool = Security(get_token)):
    check_token(token)
    async with pool.acquire_with_log(sql_logger) as db, db.transaction():
        return await PeerDB.update(db, peer_id, update)


@router.delete("/{peer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(peer_id: int,
                 pool: DBPool = Depends(db_pool),
                 token: bool = Security(get_token)):
    check_token(token)
    async with pool.acquire_with_log(sql_logger) as db, db.transaction():
        await PeerDB.delete(db, peer_id)


@router.post("/", response_model=PeerCreated,
             status_code=status.HTTP_201_CREATED)
async def create(create: PeerCreate,
                 pool: DBPool = Depends(db_pool),
                 token: bool = Security(get_token)):
    check_token(token)
    async with pool.acquire_with_log(sql_logger) as db, db.transaction():
        create = PeerDB.convert_object(create, PeerCreatePrivateKey)
        return await PeerDB.create(db, create)

