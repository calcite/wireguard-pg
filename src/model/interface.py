from ipaddress import IPv4Address, IPv4Interface, ip_interface
from typing import List, Optional
from datetime import datetime
from asyncpg import Connection
import loggate
from pydantic import BaseModel, Field, model_validator
from lib.helper import get_file_content, get_wg_private_key, get_wg_public_key, ip_range_to_ips, optimalize_ip_range
from model.base import BaseDBModel


logger = loggate.getLogger('Interface')

class InterfaceError(Exception): pass    # noqa

#################################################################################
#   InterfaceSimple
#################################################################################


class InterfaceSimpleUpdate(BaseModel):
    server_name: str = Field(max_length=64)
    interface_name: str = Field(max_length=15)
    private_key: str = Field(None, max_length=256)
    listen_port: int
    address: str = Field(max_length=256)    # Comma separated IPv4 or IPv6
    dns: Optional[str] = Field(None, max_length=256)        # Comma separated IPv4 or IPv6
    mtu: Optional[int] = Field(None)
    fw_mark: Optional[int] = Field(None)    # default is 0 = off
    # value off - disable routing, value auto is default
    table: Optional[int] = Field(None)
    pre_up: Optional[str] = Field(None)
    post_up: Optional[str] = Field(None)
    pre_down: Optional[str] = Field(None)
    post_down: Optional[str] = Field(None)      # %i is expanded as interface
    enabled: bool = Field(True)

    def get_private_key(self):
        if self.private_key.startswith('file://'):
            return get_file_content(self.private_key.replace('file://', '')).strip()
        return self.private_key


class InterfaceSimple(InterfaceSimpleUpdate):
    id: int = Field()
    updated_at: datetime = Field(default_factory=datetime.now)
    created_at: datetime = Field(default_factory=datetime.now)


class InterfaceSimpleDB(BaseDBModel):
    class Meta:
        db_table = 'server_interface'
        PYDANTIC_CLASS = InterfaceSimple
        DEFAULT_SORT_BY: str = 'id'


#################################################################################
#   InterfaceTemplate
#################################################################################

class InterfaceTemplateUpdate(BaseModel):
    public_key: str = Field(max_length=255)
    public_endpoint: str = Field(None, max_length=128)
    ip_range: str = Field(None, max_length=255)
    # ip_prefix_len: int = Field(None, min=0, max=32)
    client_dns: Optional[str] = Field(None, max_length=128)
    client_pre_up: Optional[str] = Field(None)
    client_post_up: Optional[str] = Field(None)
    client_pre_down: Optional[str] = Field(None)
    client_post_down: Optional[str] = Field(None)
    client_fw_mark: Optional[int] = Field(None)
    client_persistent_keepalive: Optional[int] = Field(None)
    client_allowed_ips: Optional[str] = Field(None)
    client_mtu: Optional[int] = Field(None)
    client_table: Optional[int] = Field(None)


class InterfaceTemplateCreate(InterfaceTemplateUpdate):
    id: int = Field()


class InterfaceTemplate(InterfaceTemplateCreate):
    pass


class InterfaceTemplateDB(BaseDBModel):
    class Meta:
        db_table = 'server_template'
        PYDANTIC_CLASS = InterfaceTemplate


#################################################################################
#   Interface
#################################################################################

class InterfaceUpdate(InterfaceSimpleUpdate, InterfaceTemplateUpdate):
    pass


class InterfaceCreate(InterfaceUpdate):

    @model_validator(mode='before')
    @classmethod
    def check_keys(cls, data) -> dict:
        if not data.get('private_key'):
            data['private_key'] = get_wg_private_key()
        elif data['private_key'].startswith('file://') and not data.get('public_key'):
            raise InterfaceError(
                'If the private key is placed in local file %s, '
                'the public key is required.',
                data['private_key']
            )
        if not data.get('public_key'):
            data['public_key'] = get_wg_public_key(data['private_key'])

        if data.get('ip_range') and (ip_range := optimalize_ip_range(data['ip_range'])):
            # Optimalize IP range
            data['ip_range'] = ip_range
        return data


class Interface(InterfaceSimpleUpdate, InterfaceTemplateUpdate):
    id: int = Field()
    updated_at: datetime = Field(default_factory=datetime.now)
    created_at: datetime = Field(default_factory=datetime.now)


class InterfaceDB(BaseDBModel):
    class Meta:
        db_table = 'server_interface'
        PYDANTIC_CLASS = Interface
        DEFAULT_SORT_BY: str = 'f.id'
        sub_sql = 'LEFT JOIN "server_template" st USING("id")'
        sub_columns = ',st.*'

    @classmethod
    async def pre_update(cls, db: Connection, interface: Interface, update: InterfaceUpdate, **kwargs):
        itemp = cls.convert_object(update, InterfaceTemplateUpdate, interface_id=interface.id)
        await InterfaceTemplateDB.update(db, interface.id, itemp)
        return cls.convert_object(update, InterfaceSimpleUpdate)

    @classmethod
    async def pre_create(cls, db: Connection, create: InterfaceCreate, **kwargs):
        return cls.convert_object(create, InterfaceSimpleUpdate)

    @classmethod
    async def post_create(cls, db: Connection, data: dict, create: InterfaceCreate, **kwargs):
        itemp = cls.convert_object(create, InterfaceTemplateCreate, id=data['id'])
        res = await InterfaceTemplateDB.create(db, itemp)
        return cls.convert_object(res, Interface, **data)

    @classmethod
    async def get_used_ips(cls, db: Connection, interface_id: int) -> List[IPv4Address]:
        rows = await db.fetch(
            'SELECT "address" FROM "client_peer" WHERE "interface_id" = $1;',
            interface_id
        )
        return [ip_interface(it['address']).ip for it in rows]

    @classmethod
    async def get_free_ips(cls, db: Connection, interface: Interface) -> List[IPv4Interface]:
        if not interface.ip_range:
            return
        ips = set(ip_range_to_ips(interface.ip_range))
        used_ips = set()
        if hasattr(interface, 'id'):
            used_ips = set(await cls.get_used_ips(db, interface.id))
        if interface.address:
            for ip in interface.address.splitlines():
                used_ips.add(ip_interface(ip).ip)
        ips = list(ips.difference(used_ips))
        ips.sort()
        return ips
