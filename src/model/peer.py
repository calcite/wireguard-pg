from ipaddress import ip_interface
from typing import Optional
from datetime import datetime
from asyncpg import Connection
from pydantic import BaseModel, Field, model_validator
from lib.helper import get_qrcode_based64, get_wg_private_key, get_wg_public_key, render_template
from model.base import BaseDBModel
from model.interface import InterfaceDB


class PeerUpdate(BaseModel):
    interface_id: int
    name: str = Field(max_length=64)
    description: Optional[str] = Field(None, max_length=256)
    public_key: str = Field(max_length=256)
    preshared_key: Optional[str] = Field(None, max_length=256)
    allowed_ips: Optional[str] = Field(None)
    address: str = Field(max_length=256)
    enabled: bool = Field(True)


class PeerCreate(PeerUpdate):
    public_key: Optional[str] = Field(None, max_length=256)
    address: Optional[str] = Field(None, max_length=256)


class PeerCreatePrivateKey(PeerCreate):
    private_key: Optional[str] = Field(None)

    @model_validator(mode='before')
    @classmethod
    def check_keys(cls, data) -> dict:
        if not data.get('public_key'):
            data['private_key'] = get_wg_private_key()
            data['public_key'] = get_wg_public_key(data['private_key'])
        return data


class PeerCreated(PeerUpdate):
    id: int
    private_key: Optional[str] = Field(None)
    client_config: Optional[str] = Field(None)
    qrcode: Optional[str] = Field(None)


class Peer(PeerUpdate):
    id: int
    updated_at: datetime
    created_at: datetime


class PeerDB(BaseDBModel):
    class Meta:
        db_table = 'client_peer'
        PYDANTIC_CLASS = Peer
        DEFAULT_SORT_BY: str = 'id'

    @classmethod
    async def pre_update(cls, db: Connection,
                         peer: Peer, update: PeerUpdate, **kwargs):
        if not update.address:
            iface = await InterfaceDB.get(db, update.interface_id)
            if ips := await InterfaceDB.get_free_ips(db, iface):
                update.address = ips.pop(0)
        update.address = str(ip_interface(update.address))

    @classmethod
    async def pre_create(cls, db: Connection,
                         create: PeerCreatePrivateKey, **kwargs):
        if not create.address:
            iface = await InterfaceDB.get(db, create.interface_id)
            if ips := await InterfaceDB.get_free_ips(db, iface):
                create.address = ips.pop(0)
        create.address = str(ip_interface(create.address))
        return cls.convert_object(create, PeerCreate)

    @classmethod
    async def post_create(cls, db: Connection, data: dict, create: PeerCreatePrivateKey, **kwargs):
        iface = await InterfaceDB.get(db, create.interface_id)
        peer: PeerCreated = cls.convert_object(create, PeerCreated, **data)
        peer.client_config = render_template(
            'client.conf.j2',
            interface=iface,
            peer=peer
        )
        peer.qrcode = get_qrcode_based64(peer.client_config)
        return peer
