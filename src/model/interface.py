from ipaddress import AddressValueError, IPv4Address, IPv4Network, collapse_addresses, summarize_address_range
import re
import subprocess
from typing import List, Optional, OrderedDict, Self
from datetime import datetime
from asyncpg import Connection
import loggate
from pydantic import BaseModel, Field, field_validator, model_validator
from config import get_config
from lib.helper import cmd, get_file_content
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
    public_endpoint: Optional[str] = Field(None, max_length=256)
    ip_range: Optional[str] = Field(None, max_length=256)
    mtu: Optional[int] = Field(None)
    fw_mark: Optional[int] = Field(None)    # default is 0 = off
    table: Optional[str] = Field(None, max_length=32)   # value off - disable routing, value auto is default
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
            blocks = re.split(',|\n',ip_range)
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
    def check_keys(cls, data) -> Self:
        if not data.get('private_key'):
            genkey_process = subprocess.run(
                ('wg', 'genkey'), capture_output=True, text=True, check=True
            )
            data['private_key'] = genkey_process.stdout.strip()
        private_key = data.get('private_key')
        if private_key.startswith('/') and not data.get('public_key'):
            raise InterfaceError(
                'If the private key is placed in local file %s, '
                'the public key is required.',
                private_key
            )
        if not data.get('public_key'):
            pubkey_process = subprocess.run(
                ('wg', 'pubkey'), input=private_key, capture_output=True,
                text=True, check=True
            )
            data['public_key'] = pubkey_process.stdout.strip()
        if ip_range := cls.validate_ip_range(data.get('ip_range')):
            data['ip_range'] = ip_range
        return data


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
        if not create.address:
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
        ips = set(interface.ip_range_to_ips(interface.ip_range))
        used_ips = set()
        if not hasattr(interface, 'id'):
            used_ips = set(await cls.get_used_ips(db, interface.id))
        if interface.address:
            used_ips.add(IPv4Address(interface.address))
        ips = list(ips.difference(used_ips))
        ips.sort()
        return ips