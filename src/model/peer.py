import subprocess
from typing import List, Optional, OrderedDict, Self
from datetime import datetime
from asyncpg import Connection
from pydantic import BaseModel, Field, model_validator
from config import get_config
from model.base import BaseDBModel, BasePModel
from model.interface import Interface, InterfaceDB

PEER_TABLE = get_config('DATABASE_PEER_TABLE_NAME')


class PeerUpdate(BaseModel):
    interface_id: int
    name: str = Field(max_length=64)
    description: Optional[str] = Field(None, max_length=256)
    public_key: str = Field(max_length=256)
    preshared_key: Optional[str] = Field(None, max_length=256)
    persistent_keepalive: Optional[int] = Field(None)
    allowed_ips: str = Field(max_length=512)    # Comma separated IPv4 or IPv6
    endpoint: Optional[str] = Field(None, max_length=256)
    address: Optional[str] = Field(None, max_length=256)    # Comma separated IPv4 or IPv6
    enabled: bool = Field(True)


class PeerCreate(BaseModel):
    interface_id: int
    name: str = Field(max_length=64)
    description: Optional[str] = Field(None, max_length=256)
    public_key: Optional[str] = Field(None, max_length=256)
    preshared_key: Optional[str] = Field(None, max_length=256)
    persistent_keepalive: Optional[int] = Field(None)
    allowed_ips: str = Field(max_length=512)    # Comma separated IPv4 or IPv6
    endpoint: Optional[str] = Field(None, max_length=256)
    address: Optional[str] = Field(None, max_length=256)    # Comma separated IPv4 or IPv6
    enabled: bool = Field(True)

class PeerCreated(PeerUpdate):
    id: int
    private_key: Optional[str] = Field(None)
    client_config: Optional[str] = Field(None)
    updated_at: datetime
    created_at: datetime

    def generate_client_config(self, interface: Interface) -> str:
        res = list()
        res.append('[Interface]')
        res.append(f'PrivateKey = {self.private_key}')
        res.append(f'# PublicKey = {self.public_key}')
        res.append(f'Address = {self.address}')
        if interface.dns:
            res.append(f'DNS = {self.dns}')
        res.append('')
        res.append('[Peer]')
        res.append(f'PublicKey = {interface.public_key}')
        if endpoint := self.endpoint or interface.public_endpoint:
            res.append(f'Endpoint = {endpoint}')
        res.append(f'AllowedIPs = {self.allowed_ips}')
        if self.persistent_keepalive:
            res.append(f'PersistentKeepalive = {self.persistent_keepalive}')
        if self.preshared_key:
            res.append(f'PresharedKey = {self.preshared_key}')
        self.client_config = '\n'.join(res)

class Peer(PeerUpdate):
    id: int
    updated_at: datetime
    created_at: datetime

    def get_config(self) -> List[str]:
        res = OrderedDict()
        res['PublicKey'] = self.public_key
        if self.preshared_key:
            res['PresharedKey'] = self.preshared_key
        res['AllowedIPs'] = self.allowed_ips
        if self.endpoint:
            res['Endpoint'] = self.endpoint
        if self.persistent_keepalive:
            res['PersistentKeepalive'] = self.persistent_keepalive
        res['# IP'] = self.address

        resL = [f'[Peer]  # Name: {self.name}']
        for k, v in res.items():
            resL.append(f'{k} = {v}')
        return resL


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

