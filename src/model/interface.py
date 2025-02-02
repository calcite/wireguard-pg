from ipaddress import AddressValueError, IPv4Address, IPv4Network, \
    collapse_addresses, summarize_address_range
import re
from typing import List, Optional
from datetime import datetime
from asyncpg import Connection
import loggate
from pydantic import BaseModel, Field, model_validator
from config import get_config
from lib.helper import get_file_content, get_wg_private_key, get_wg_public_key
from model.base import BaseDBModel, BasePModel

INTERFACE_TABLE = get_config('DATABASE_INTERFACE_TABLE_NAME')

logger = loggate.getLogger('Interface')

class InterfaceError(Exception): pass    # noqa


class InterfaceUpdate(BaseModel):
    server_name: str = Field(max_length=64)
    interface_name: str = Field(max_length=64)
    private_key: Optional[str] = Field(None, max_length=256)
    public_key: Optional[str] = Field(max_length=256)
    listen_port: int
    address: Optional[str] = Field(None, max_length=256)    # Comma separated IPv4 or IPv6
    dns: Optional[str] = Field(None, max_length=256)        # Comma separated IPv4 or IPv6
    public_endpoint: str = Field(None, max_length=256)
    ip_range: Optional[str] = Field(None, max_length=256)
    mtu: Optional[int] = Field(None)
    fw_mark: Optional[int] = Field(None)    # default is 0 = off
    # value off - disable routing, value auto is default
    table: Optional[str] = Field(None, max_length=32)
    pre_up: Optional[str] = Field(None)
    post_up: Optional[str] = Field(None)
    pre_down: Optional[str] = Field(None)
    post_down: Optional[str] = Field(None)      # %i is expanded as interface
    enabled: bool = Field(True)

    @classmethod
    def ip_range_to_ips(cls, ip_range: Optional[str]) -> List[IPv4Network]:
        if not ip_range:
            return []
        try:
            blocks = re.split(',|\n', ip_range)
            nets = []
            for range in blocks:
                ips = [IPv4Address(ip.strip()) for ip in range.split('-')]
                if len(ips) == 1:
                    nets.append(ips[0])
                elif len(ips) == 2:
                    nets.extend(summarize_address_range(*ips))
                else:
                    raise ValueError(f'Unknown format of range: {range}')
            nets = collapse_addresses(nets)
            ips = set()
            for net in nets:
                ips.add(net.network_address)
                ips.update(net.hosts())
                ips.add(net.broadcast_address)
            return sorted(list(ips))
        except AddressValueError as e:
            raise ValueError(str(e))

    @classmethod
    def validate_ip_range(cls, ip_range) -> str:
        if not ip_range:
            return
        ips = cls.ip_range_to_ips(ip_range)
        ips_copy = set(ips)
        res = []
        last = None
        start = None
        while ips and (ip := ips.pop(0)):
            if not ip.is_private:
                raise ValueError(f'IP {ip} is not private')
            if last != ip - 1:
                if start:
                    res.append(f'{start} - {last}')
                start = ip
            last = ip
        if start:
            if start != last:
                res.append(f'{start} - {last}')
            else:
                res.append(f'{start}')
        new_range = '\n'.join(res)
        new_ips = cls.ip_range_to_ips(new_range)
        diff = set(new_ips).difference(set(ips_copy))
        if diff:
            t1 = cls.ip_range.replace("\n", ",")
            t2 = new_range.replace("\n", ",")
            logger.warning(
                'Original range %s is not equal to new range %s.',
                t1, t2
            )
            return
        if len(ip_range) < len(new_range):
            return new_range

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
        if ip_range := cls.validate_ip_range(data.get('ip_range')):
            data['ip_range'] = ip_range
        return data


class InterfaceCreate(InterfaceUpdate):
    pass


class Interface(InterfaceCreate, BasePModel):
    updated_at: datetime = Field(default_factory=datetime.now)
    created_at: datetime = Field(default_factory=datetime.now)

    def get_private_key(self):
        if self.private_key.startswith('file://'):
            return get_file_content(self.private_key.replace('file://', '')).strip()
        return self.private_key


class InterfaceDB(BaseDBModel):
    class Meta:
        db_table = INTERFACE_TABLE
        PYDANTIC_CLASS = Interface
        DEFAULT_SORT_BY: str = 'id'

    @classmethod
    async def pre_update(cls, db: Connection,
                         interface: Interface, update: InterfaceUpdate, **kwargs):
        if not update.address:
            ips = set(update.ip_range_to_ips(update.ip_range))
            used_ips = set(await cls.get_used_ips(db, interface.id))
            ips = list(ips.difference(used_ips))
            ips.sort()
            update.address = str(ips.pop(0))

    @classmethod
    async def pre_create(cls, db: Connection,
                         create: InterfaceCreate, **kwargs):
        if not create.address and create.ip_range:
            ips = list(create.ip_range_to_ips(create.ip_range))
            ips.sort()
            create.address = str(ips.pop(0))

    @classmethod
    async def get_used_ips(cls, db: Connection, interface_id: int) -> List[IPv4Address]:
        rows = await db.fetch(
            'SELECT "address" FROM "peer" WHERE "interface_id" = $1;',
            interface_id
        )
        return [IPv4Address(it['address']) for it in rows]

    @classmethod
    async def get_free_ips(cls, db: Connection, interface: Interface) -> List[IPv4Address]:
        if not interface.ip_range:
            return
        ips = set(interface.ip_range_to_ips(interface.ip_range))
        used_ips = set()
        if hasattr(interface, 'id'):
            used_ips = set(await cls.get_used_ips(db, interface.id))
        if interface.address:
            used_ips.add(IPv4Address(interface.address))
        ips = list(ips.difference(used_ips))
        ips.sort()
        return ips
