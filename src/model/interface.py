from typing import Optional, OrderedDict
from datetime import datetime
from pydantic import BaseModel, Field
from config import get_config
from lib.helper import get_file_content
from model.base import BaseDBModel, BasePModel

INTERFACE_TABLE = get_config('DATABASE_INTERFACE_TABLE_NAME')


class InterfaceUpdate(BaseModel):
    server_name: str = Field(max_length=64)
    interface_name: str = Field(max_length=64)
    private_key: Optional[str] = Field(None, max_length=256)
    public_key: str = Field(max_length=256)
    listen_port: int
    address: str = Field(max_length=256)    # Comma separated IPv4 or IPv6
    dns: Optional[str] = Field(max_length=256)        # Comma separated IPv4 or IPv6
    public_endpoint: Optional[str] = Field(None, max_length=256)
    subnet: Optional[str] = Field(None, max_length=256)
    mtu: Optional[int] = Field(None)
    fw_mark: Optional[int] = Field(None)    # default is 0 = off
    table: Optional[str] = Field(None, max_length=32)   # value off - disable routing, value auto is default
    pre_up: Optional[str] = Field(None)
    post_up: Optional[str] = Field(None)
    pre_down: Optional[str] = Field(None)
    post_down: Optional[str] = Field(None)      # %i is expanded as interface
    enabled: bool = Field(True)


class InterfaceCreate(InterfaceUpdate):
    updated_at: datetime = Field(default_factory=datetime.now)
    created_at: datetime = Field(default_factory=datetime.now)


class Interface(InterfaceCreate, BasePModel):

    def get_private_key(self):
        if self.private_key.startswith('/'):
            return get_file_content(self.private_key)
        return self.private_key

    def get_config(self, full: bool = False) -> str:
        res = OrderedDict()
        res['PrivateKey'] = self.get_private_key()
        res['# PublicKey'] = self.public_key
        res['ListenPort'] = self.listen_port
        if self.fw_mark:
            res['FwMark'] = self.fw_mark
        if full:
            res['Address'] = self.address
            if self.dns:
                res['DNS'] = self.dns
            if self.mtu:
                res['MTU'] = self.mtu
            if self.table:
                res['Table'] = self.table
            if self.pre_up:
                res['PreUp'] = self.pre_up
            if self.post_up:
                res['PostUp'] = self.post_up
            if self.pre_down:
                res['PreDown'] = self.pre_down
            if self.post_down:
                res['PostDown'] = self.post_down
        resL = ['[Interface]']
        for k, v in res.items():
            resL.append(f'{k} = {v}')
        return resL


class InterfaceDB(BaseDBModel):
    class Meta:
        db_table = INTERFACE_TABLE
        PYDANTIC_CLASS = Interface
        DEFAULT_SORT_BY: str = 'id'
