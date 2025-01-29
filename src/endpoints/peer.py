from typing import List
from asyncpg import Pool
import loggate
from fastapi import APIRouter, Depends, Security, status

from endpoints import check_token
from lib.helper import get_wg_private_key, get_wg_public_key
from model.formatter import ConfigFormatter
from model.interface import InterfaceDB
from model.peer import PeerCreated, PeerDB, Peer, PeerUpdate, PeerCreate
from lib.db import db_pool, db_logger

router = APIRouter(tags=["peer"])
sql_logger = 'sql.peer'
logger = loggate.getLogger('Peer')


@router.get("/", response_model=List[Peer])
async def gets(pool: Pool = Depends(db_pool),
               checked: bool = Security(check_token)):
    async with pool.acquire() as db, db_logger(sql_logger, db):
        return await PeerDB.gets(db)


@router.get("/{peer_id}", response_model=Peer)
async def get(peer_id: int, pool: Pool = Depends(db_pool),
              checked: bool = Security(check_token)):
    async with pool.acquire() as db, db_logger(sql_logger, db):
        return await PeerDB.get(db, peer_id)


@router.put("/{peer_id}", response_model=Peer)
async def update(peer_id: int, update: PeerUpdate,
                 pool: Pool = Depends(db_pool),
                 checked: bool = Security(check_token)):
    async with pool.acquire() as db, db.transaction(), db_logger(sql_logger, db):
        return await PeerDB.update(db, peer_id, update)


@router.delete("/{peer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(peer_id: int,
                 pool: Pool = Depends(db_pool),
                 checked: bool = Security(check_token)):
    async with pool.acquire() as db, db.transaction(), db_logger(sql_logger, db):
        await PeerDB.delete(db, peer_id)


@router.post("/", response_model=PeerCreated,
             status_code=status.HTTP_201_CREATED)
async def create(create: PeerCreate,
                 pool: Pool = Depends(db_pool),
                 checked: bool = Security(check_token)):
    async with pool.acquire() as db, db.transaction(), db_logger(sql_logger, db):
        private_key = None
        if not create.public_key:
            private_key = get_wg_private_key()
            create.public_key = get_wg_public_key(private_key)
        peer: Peer = await PeerDB.create(db, create)
        interface = await InterfaceDB.get(db, create.interface_id)
        peer = PeerCreated(**peer.model_dump(exclude_unset=True), private_key=private_key)
        peer.client_config = ConfigFormatter.get_client_configuration(peer, interface)
        return peer
