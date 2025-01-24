from typing import List, Optional, OrderedDict
from datetime import datetime
from pydantic import BaseModel, Field
from config import get_config
from model.base import BaseDBModel, BasePModel

PEER_TABLE = get_config('DATABASE_PEER_TABLE_NAME')


class PeerUpdate(BaseModel):
    interface_id: int
    name: str = Field(max_length=64)
    description: Optional[str] = Field(max_length=256)
    private_key: Optional[str] = Field(None, max_length=256)
    public_key: str = Field(max_length=256)
    preshared_key: Optional[str] = Field(max_length=256)
    persistent_keepalive: Optional[int] = Field(None)
    allowed_ips: str = Field(max_length=512)    # Comma separated IPv4 or IPv6
    endpoint: Optional[str] = Field(None, max_length=256)
    address: str = Field(max_length=256)    # Comma separated IPv4 or IPv6
    enabled: bool = Field(True)


class PeerCreate(PeerUpdate):
    updated_at: datetime = Field(default_factory=datetime.now)
    created_at: datetime = Field(default_factory=datetime.now)


class Peer(PeerCreate, BasePModel):

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
