from typing import Optional
from datetime import datetime
from asyncpg import Connection
from pydantic import BaseModel, Field
from config import get_config
from model.base import BaseDBModel
from model.interface import InterfaceDB

PEER_TABLE = get_config('DATABASE_PEER_TABLE_NAME')


class PeerUpdate(BaseModel):
    interface_id: int
    name: str = Field(max_length=64)
    description: Optional[str] = Field(None, max_length=256)
    public_key: str = Field(max_length=256)
    preshared_key: Optional[str] = Field(None, max_length=256)
    persistent_keepalive: Optional[int] = Field(None)
    allowed_ips: str = Field('0.0.0.0/0', max_length=512)    # Comma separated IPv4 or IPv6
    address: Optional[str] = Field(None, max_length=256)    # Comma separated IPv4 or IPv6
    enabled: bool = Field(True)


class PeerCreate(BaseModel):
    interface_id: int
    name: str = Field(max_length=64)
    description: Optional[str] = Field(None, max_length=256)
    public_key: Optional[str] = Field(None, max_length=256)
    preshared_key: Optional[str] = Field(None, max_length=256)
    persistent_keepalive: Optional[int] = Field(None)
    allowed_ips: str = Field('0.0.0.0/0', max_length=512)    # Comma separated IPv4 or IPv6
    address: Optional[str] = Field(None, max_length=256)    # Comma separated IPv4 or IPv6
    enabled: bool = Field(True)


class PeerCreated(PeerUpdate):
    id: int
    private_key: Optional[str] = Field(None)
    client_config: Optional[str] = Field(None)
    updated_at: datetime
    created_at: datetime


class Peer(PeerUpdate):
    id: int
    updated_at: datetime
    created_at: datetime


class PeerDB(BaseDBModel):
    class Meta:
        db_table = PEER_TABLE
        PYDANTIC_CLASS = Peer
        DEFAULT_SORT_BY: str = 'id'

    @classmethod
    async def pre_update(cls, db: Connection,
                         peer: Peer, update: PeerUpdate, **kwargs):
        if not update.address:
            iface = await InterfaceDB.get(db, update.interface_id)
            if ips := await InterfaceDB.get_free_ips(db, iface):
                update.address = str(ips.pop(0))

    @classmethod
    async def pre_create(cls, db: Connection,
                         create: PeerCreate, **kwargs):
        if not create.address:
            iface = await InterfaceDB.get(db, create.interface_id)
            if ips := await InterfaceDB.get_free_ips(db, iface):
                create.address = str(ips.pop(0))
