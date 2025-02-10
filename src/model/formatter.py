

from typing import List, OrderedDict
from model.interface import Interface
from model.peer import Peer, PeerCreated


class ConfigFormatter:

    @classmethod
    def get_server_configuration(cls, interface: Interface, peers: List[Peer],
                                 full: bool = False) -> List[str]:
        res = OrderedDict()
        res['PrivateKey'] = interface.get_private_key()
        if full:
            res['# PublicKey'] = interface.public_key
        res['ListenPort'] = interface.listen_port
        if interface.fw_mark:
            res['FwMark'] = interface.fw_mark
        if full:
            res['Address'] = interface.address
            # if interface.dns:
            #     res['DNS'] = interface.dns
            if interface.mtu:
                res['MTU'] = interface.mtu
            if interface.table:
                res['Table'] = interface.table
            if interface.pre_up:
                res['PreUp'] = interface.pre_up
            if interface.post_up:
                res['PostUp'] = interface.post_up
            if interface.pre_down:
                res['PreDown'] = interface.pre_down
            if interface.post_down:
                res['PostDown'] = interface.post_down
        resL = ['[Interface]']
        for k, v in res.items():
            resL.append(f'{k} = {v}')

        for peer in peers:
            resL.append('')
            if full:
                resL.append(f'[Peer]  # Name: {peer.name} ({peer.address})')
            else:
                resL.append('[Peer]')
            resL.append(f'PublicKey = {peer.public_key}')
            if peer.preshared_key:
                resL.append(f'PresharedKey = {peer.preshared_key}')
            resL.append(f'AllowedIPs = {peer.address}/32')
            if peer.persistent_keepalive:
                resL.append(f'PersistentKeepalive = {peer.persistent_keepalive}')
        if full:
            resL.append('')
        return resL

    @classmethod
    def get_client_configuration(cls, peer: PeerCreated, interface: Interface,
                                 line_separator='/n') -> str:
        res = list()
        res.append('[Interface]')
        res.append(f'PrivateKey = {peer.private_key}')
        res.append(f'# PublicKey = {peer.public_key}')
        res.append(f'Address = {peer.address}')
        if interface.dns:
            res.append(f'DNS = {interface.dns}')
        res.append('')
        res.append('[Peer]')
        res.append(f'PublicKey = {interface.public_key}')
        if interface.public_endpoint:
            res.append(f'Endpoint = {interface.public_endpoint}')
        res.append(f'AllowedIPs = {peer.allowed_ips}')
        if peer.persistent_keepalive:
            res.append(f'PersistentKeepalive = {peer.persistent_keepalive}')
        if peer.preshared_key:
            res.append(f'PresharedKey = {peer.preshared_key}')
        return line_separator.join(res)
