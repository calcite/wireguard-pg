import asyncio
import json
import os
from pathlib import Path
import subprocess
from typing import List
from asyncpg import Connection, Pool
from loggate import getLogger

from config import get_config
from lib.db import DBConnection, db_logger
from model.interface import Interface, InterfaceDB
from model.peer import Peer, PeerDB


WIREGUARD_CONFIG_FOLDER = get_config('WIREGUARD_CONFIG_FOLDER', wrapper=Path)

logger = getLogger('server')

class WGServer:

    @staticmethod
    def get_iface_from_config(path: str):
        return os.path.basename(path).replace('.conf', '')

    def __init__(self, server_name: str) -> None:
        self.server_name = server_name
        self.interface_ids = set()
        DBConnection.register_notification('interface', self.notification_interface)
        DBConnection.register_notification('peer', self.notification_peer)

    def cmd(self, *args, capture_output=True, ignore_error=False) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(
                args, text=True, check=True, capture_output=capture_output
            )
        except subprocess.CalledProcessError as e:
            if not ignore_error:
                logger.error(e.stderr)
        return None

    def create_config(self, iface: Interface, peers: List[Peer], folder: str,
                      full: bool) -> str:
        file_name = f'{folder}/{iface.interface_name}.conf'
        desc = os.open(
            path=file_name,
            flags = (
                os.O_WRONLY |
                os.O_CREAT |
                os.O_TRUNC
            ),
            mode=0o700
        )
        with open(desc, 'w+') as fd:
            fd.write('\n'.join(iface.get_config(full=full)))
            fd.write('\n')
            for peer in peers:
                if peer.enabled:
                    fd.write('\n')
                    fd.write('\n'.join(peer.get_config()))
                    fd.write('\n')
        return file_name

    def is_interface_exist(self, iface):
        res = self.cmd('ip', 'link', 'show')
        return res and res.returncode == 0

    def interface_down(self, iface):
        if self.is_interface_exist(iface):
            logger.info('Stop interface %s', iface)
            res = self.cmd('wg-quick', 'down', iface)
            if not res or res.returncode != 0:
                logger.warning('Problem with stopping interface.')

    def interface_up(self, iface):
        self.interface_down(iface)
        logger.info('Start interface %s', iface)
        res = self.cmd('wg-quick', 'up', iface)
        if not res or res.returncode != 0:
            logger.warning('Problem with starting interface %s.', iface)

    async def start_server(self, db_conn: DBConnection):
        logger.info('Starting server')
        WIREGUARD_CONFIG_FOLDER.mkdir(parents=True, exist_ok=True)
        if db_conn.pool:
            async with db_conn.pool.acquire() as db, db_logger('server', db):
                ifaces = await InterfaceDB.gets(
                    db, 'server_name=$1 AND enabled=true', self.server_name
                )
                for iface in ifaces:
                    logger.debug('Update config for %s', iface.interface_name)
                    self.interface_ids.add(iface.id)
                    peers = await PeerDB.gets(
                        db, 'interface_id=$1 AND enabled=true', iface.id
                    )
                    self.create_config(
                        iface, peers, WIREGUARD_CONFIG_FOLDER, True
                    )
        for conf in WIREGUARD_CONFIG_FOLDER.glob('*.conf'):
            logger.info('Load %s', conf)
            iface = self.get_iface_from_config(conf)
            self.interface_up(iface)


    async def notification_interface(self, db: Connection, channel, payload):
        logger.debug('interface DB event: %s', payload)
        payload = json.loads(payload)
        new_row = payload.get('new')
        if not new_row:
            new_row = {}
        old_row = payload.get('old')
        if not old_row:
            old_row = {}
        if not new_row or not new_row.get('enabled'):
            # interface deleted or disabled
            iface = old_row.get('name')
            logger.info('Interface %s was deleted.', iface)
            self.interface_down(iface.interface_name)
            os.remove('{WIREGUARD_CONFIG_FOLDER}/{iface}.conf')
            return
        iface = Interface(**new_row)
        peers = await PeerDB.gets(
            db, 'interface_id=$1 AND enabled=true', iface.id
        )
        self.create_config(
            iface, peers, WIREGUARD_CONFIG_FOLDER, True
        )
        self.interface_up(iface.interface_name)


    async def notification_peer(self, db: Connection, channel, payload):
        logger.debug('Peer DB event: %s', payload)
        payload = json.loads(payload)
        new_row = payload.get('new')
        if not new_row:
            new_row = {}
        old_row = payload.get('old')
        if not old_row:
            old_row = {}
        interface_id = new_row.get('interface_id', old_row.get('interface_id'))
        if interface_id in self.interface_ids:
            iface = await InterfaceDB.get(db, interface_id)
            if not iface.enabled:
                return
            peers = await PeerDB.gets(
                db, 'interface_id=$1 AND enabled=true', iface.id
            )
            tmp_config_file = self.create_config(iface, peers, '/tmp', False)
            res = self.cmd(
                'wg', 'syncconf', iface.interface_name, tmp_config_file
            )
            if not res or res.returncode != 0:
                logger.warning(
                    'Problem updating interface %s.', iface.interface_name
                )
            self.create_config(iface, peers, WIREGUARD_CONFIG_FOLDER, True)
            if not self.is_interface_exist(iface.interface_name):
                self.interface_up(iface.interface_name)

