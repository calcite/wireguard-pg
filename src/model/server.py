import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import List
from asyncpg import Connection
from loggate import getLogger

from config import get_config
from lib.db import DBConnection, db_logger
from lib.helper import checksum, cmd, get_file_content, render_template, write_file
from model.interface import InterfaceSimple, InterfaceSimpleDB
from model.peer import PeerDB


WIREGUARD_CONFIG_FOLDER = get_config('WIREGUARD_CONFIG_FOLDER', wrapper=Path)

logger = getLogger('wgserver')


class WGServer:

    @staticmethod
    def get_iface_from_config(path: str | Path):
        return os.path.basename(path).replace('.conf', '') if str(path).endswith('.conf') else path

    @staticmethod
    def get_config_from_iface(iface: str | Path, path: Path = WIREGUARD_CONFIG_FOLDER) -> Path:
        if str(iface).endswith('.conf'):
            return iface
        return path.joinpath(f'{iface}.conf')

    @staticmethod
    def get_local_config_files() -> List[Path]:
        WIREGUARD_CONFIG_FOLDER.mkdir(parents=True, exist_ok=True)
        return WIREGUARD_CONFIG_FOLDER.glob('*.conf')

    def __init__(self, server_name: str) -> None:
        self.server_name = server_name
        self.interface_ids = set()
        DBConnection.register_notification('server_interface', self.notification_interface)
        DBConnection.register_notification('client_peer', self.notification_peer)

    def is_interface_exist(self, iface: str):
        iface = self.get_iface_from_config(iface)
        res = cmd('ip', 'link', 'show', iface, ignore_error=True)
        return res and res.returncode == 0

    def interface_down(self, iface):
        if self.is_interface_exist(iface):
            iface = self.get_config_from_iface(iface)
            logger.info('Stop interface %s', iface)
            res = cmd('wg-quick', 'down', str(iface))
            if not res or res.returncode != 0:
                logger.warning('Problem with stopping interface.')

    def interface_up(self, iface, force: bool = False):
        if self.is_interface_exist(iface) and not force:
            return
        iface = self.get_config_from_iface(iface)
        self.interface_down(iface)
        logger.info('Start interface %s', iface)
        res = cmd('wg-quick', 'up', str(iface))
        if not res or res.returncode != 0:
            logger.warning('Problem with starting interface %s.', iface)

    async def start_server(self, db_conn: DBConnection):
        logger.info('Starting Wireguard server')
        if db_conn.pool:
            conf_files = {it: checksum(get_file_content(it)) for it in self.get_local_config_files()}
            force_update = set()

            async with db_conn.pool.acquire() as db, db_logger('server', db):
                ifaces = await InterfaceSimpleDB.gets(
                    db, 'server_name=$1 AND enabled=true', self.server_name, _pydantic_class=InterfaceSimple
                )
                for iface in ifaces:
                    # Create / update configuration files
                    self.interface_ids.add(iface.id)
                    peers = await PeerDB.gets(
                        db, 'interface_id=$1 AND enabled=true', iface.id
                    )
                    conf_file = self.get_config_from_iface(iface.interface_name)
                    content = render_template(
                        'interface_full.conf.j2',
                        interface=iface,
                        peers=peers
                    )
                    if checksum(content) != conf_files.get(conf_file):
                        logger.debug('Update config for %s', iface.interface_name)
                        write_file(conf_file, content, 0o700)
                        force_update.add(conf_file)
                    if conf_file in conf_files:
                        conf_files.pop(conf_file)
                for conf in conf_files.keys():
                    # Remove old configuration files
                    self.__remove_interface(conf)

        for conf in self.get_local_config_files():
            # Start available configuration files
            logger.info('Load %s', conf)
            self.interface_up(conf, conf in force_update)

    async def stop_server(self, db_conn: DBConnection):
        logger.info('The application is stopped. Wireguard interfaces are still running.')

    def __remove_interface(self, iface: str | Path):
        self.interface_down(iface)
        conf_file = self.get_config_from_iface(iface)
        conf_file.unlink(True)
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
            iface = InterfaceSimple(**new_row)
            old_interface_name = old_row.get('interface_name')
            if old_interface_name and iface.interface_name != old_interface_name:
                # Rename interface
                self.__remove_interface(old_interface_name)
            peers = await PeerDB.gets(db, 'interface_id=$1 AND enabled=true', iface.id)
            conf_file = self.get_config_from_iface(iface.interface_name)
            content = render_template(
                'interface_full.conf.j2',
                interface=iface,
                peers=peers
            )
            if checksum(content) != checksum(get_file_content(conf_file)):
                logger.debug('Update config for %s', iface.interface_name)
                write_file(conf_file, content, 0o700)
                self.interface_up(iface.interface_name, True)
            self.interface_ids.add(iface.id)

        if (new_server_name != old_server_name or not new_enabled) \
                and old_server_name == self.server_name:
            # Delete, Move or Disabled
            if old_row['id'] in self.interface_ids:
                self.interface_ids.remove(old_row['id'])
            self.__remove_interface(old_row.get('interface_name'))

    async def __update_peer(self, db: Connection, iface_id: int):
        iface = await InterfaceSimpleDB.get(
            db,
            'id = $1 AND server_name = $2 AND enabled=true ',
            iface_id, self.server_name
        )
        if not iface:
            return
        peers = await PeerDB.gets(
            db, 'interface_id=$1 AND enabled=true', iface.id
        )
        logger.info('Update config for %s', iface.interface_name)
        content = render_template(
            'interface_update.conf.j2',
            interface=iface,
            peers=peers
        )
        with NamedTemporaryFile('w') as tmp_fd:
            tmp_fd.write(content)
            tmp_fd.flush()
            res = cmd('wg', 'syncconf', iface.interface_name, tmp_fd.name)
            if not res or res.returncode != 0:
                logger.warning(
                    'Problem updating interface %s.', iface.interface_name
                )
        conf_file = self.get_config_from_iface(iface.interface_name)
        content = render_template(
            'interface_full.conf.j2',
            interface=iface,
            peers=peers
        )
        if checksum(content) != checksum(get_file_content(conf_file)):
            write_file(conf_file, content, 0o700)
        if not self.is_interface_exist(iface.interface_name):
            self.interface_up(conf_file)

    async def notification_peer(self, db: Connection, channel, payload):
        logger.debug('Peer DB event: %s', payload)
        payload = json.loads(payload)
        old_iface_id = (payload.get('old') or {}).get('interface_id')
        iface_id = (payload.get('new') or {}).get('interface_id') or old_iface_id
        if old_iface_id and iface_id != old_iface_id:
            await self.__update_peer(db, old_iface_id)
        await self.__update_peer(db, iface_id)
