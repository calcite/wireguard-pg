import json
import os
from pathlib import Path
from typing import List
from asyncpg import Connection
from loggate import getLogger

from config import get_config
from lib.db import DBConnection, db_logger
from lib.helper import cmd
from model.formatter import ConfigFormatter
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

    def create_config(self, iface: Interface, peers: List[Peer], folder: str,
                      full: bool) -> str:
        file_name = f'{folder}/{iface.interface_name}.conf'
        desc = os.open(
            path=file_name,
            flags=(
                os.O_WRONLY |
                os.O_CREAT |
                os.O_TRUNC
            ),
            mode=0o700
        )
        with open(desc, 'w') as fd:
            fd.write(
                os.linesep.join(ConfigFormatter.get_server_configuration(iface, peers, full))
            )
        return file_name

    def is_interface_exist(self, iface: str):
        res = cmd('ip', 'link', 'show', iface, ignore_error=True)
        return res and res.returncode == 0

    def interface_down(self, iface):
        if self.is_interface_exist(iface):
            logger.info('Stop interface %s', iface)
            res = cmd('wg-quick', 'down', iface)
            if not res or res.returncode != 0:
                logger.warning('Problem with stopping interface.')

    def interface_up(self, iface):
        self.interface_down(iface)
        logger.info('Start interface %s', iface)
        res = cmd('wg-quick', 'up', iface)
        if not res or res.returncode != 0:
            logger.warning('Problem with starting interface %s.', iface)

    async def start_server(self, db_conn: DBConnection):
        logger.info('Starting Wireguard server')
        WIREGUARD_CONFIG_FOLDER.mkdir(parents=True, exist_ok=True)
        if db_conn.pool:
            conf_files = set(str(it) for it in WIREGUARD_CONFIG_FOLDER.glob('*.conf'))
            async with db_conn.pool.acquire() as db, db_logger('server', db):
                ifaces = await InterfaceDB.gets(
                    db, 'server_name=$1 AND enabled=true', self.server_name
                )
                for iface in ifaces:
                    # Create / update configuration files
                    logger.debug('Update config for %s', iface.interface_name)
                    self.interface_ids.add(iface.id)
                    peers = await PeerDB.gets(
                        db, 'interface_id=$1 AND enabled=true', iface.id
                    )
                    conf_file = self.create_config(
                        iface, peers, WIREGUARD_CONFIG_FOLDER, True
                    )
                    if conf_file in conf_files:
                        conf_files.remove(conf_file)
                for conf in conf_files:
                    # Remove old configuration files
                    self.__remove_interface(self.get_iface_from_config(conf))

        for conf in WIREGUARD_CONFIG_FOLDER.glob('*.conf'):
            # Start available configuration files
            logger.info('Load %s', conf)
            iface = self.get_iface_from_config(conf)
            self.interface_up(iface)

    async def stop_server(self, db_conn: DBConnection):
        logger.info('The application is stopped. Wireguard interfaces are still running.')

    def __remove_interface(self, iface: str):
        self.interface_down(iface)
        if os.path.exists(f'{WIREGUARD_CONFIG_FOLDER}/{iface}.conf'):
            os.remove(f'{WIREGUARD_CONFIG_FOLDER}/{iface}.conf')
            logger.info('Interface %s was deleted.', iface)

    async def notification_interface(self, db: Connection, channel, payload):
        logger.debug('interface DB event: %s', payload)
        payload = json.loads(payload)
        new_row = payload.get('new') or {}
        old_row = payload.get('old') or {}
        new_enabled = new_row.get('enabled')
        new_server_name = new_row.get('server_name')
        old_server_name = old_row.get('server_name')

        if new_server_name and new_server_name == self.server_name and new_enabled:
            # Update or Add
            iface = Interface(**new_row)
            peers = await PeerDB.gets(
                db, 'interface_id=$1 AND enabled=true', iface.id
            )
            self.create_config(
                iface, peers, WIREGUARD_CONFIG_FOLDER, True
            )
            self.interface_ids.add(iface.id)
            self.interface_up(iface.interface_name)

        if (new_server_name != old_server_name or not new_enabled) \
                and old_server_name == self.server_name:
            # Delete, Move or Disabled
            if old_row['id'] in self.interface_ids:
                self.interface_ids.remove(old_row['id'])
            self.__remove_interface(old_row.get('interface_name'))

    def __update_peer_configs(self, iface: Interface, peers: List[Peer]):
        tmp_config_file = self.create_config(iface, peers, '/tmp', False)
        res = cmd(
            'wg', 'syncconf', iface.interface_name, tmp_config_file
        )
        if not res or res.returncode != 0:
            logger.warning(
                'Problem updating interface %s.', iface.interface_name
            )
        self.create_config(iface, peers, WIREGUARD_CONFIG_FOLDER, True)
        if not self.is_interface_exist(iface.interface_name):
            self.interface_up(iface.interface_name)

    async def notification_peer(self, db: Connection, channel, payload):
        logger.debug('Peer DB event: %s', payload)
        payload = json.loads(payload)
        new_row = payload.get('new') or {}
        old_row = payload.get('old') or {}
        iface_old_id = new_row.get('interface_id')
        iface_new_id = old_row.get('interface_id')
        if iface_new_id in self.interface_ids:
            # Add or Update peer
            iface = await InterfaceDB.get(db, iface_new_id)
            if not iface or not iface.enabled:
                return
            peers = await PeerDB.gets(
                db, 'interface_id=$1 AND enabled=true', iface.id
            )
            self.__update_peer_configs(iface, peers)
        if iface_new_id != iface_old_id and iface_old_id in self.interface_ids:
            # Delete or Move
            iface = await InterfaceDB.get(db, iface_old_id)
            if not iface or not iface.enabled:
                return
            peers = await PeerDB.gets(
                db, 'interface_id=$1 AND enabled=true', iface.id
            )
            self.__update_peer_configs(iface, peers)
