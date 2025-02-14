import base64
import hashlib
import io
from ipaddress import AddressValueError, IPv4Address, collapse_addresses, ip_interface, summarize_address_range
import os
import re
import subprocess
from typing import List, Optional
import jinja2
import loggate
import qrcode
from qrcode.image.pure import PyPNGImage
import yaml

environment = jinja2.Environment(loader=jinja2.FileSystemLoader("templates/"))
environment.filters['ip'] = lambda x: ip_interface(x).ip


def render_template(template: str, **kwargs) -> str:
    return environment.get_template(template).render(**kwargs)


def checksum(content: str) -> str:
    return str(hashlib.md5(content.encode()).hexdigest()) if content else None


def get_yaml(filename):
    with open(filename, 'r') as fd:
        return yaml.safe_load(fd)


def get_file_content(filename) -> str:
    if not os.path.exists(filename):
        return None
    with open(filename, 'r') as fd:
        return fd.read()


def write_file(file_name: str, content: str, mode: int = 0o777):
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
        fd.write(content)


def dict_bytes2str(dd):
    res = {}
    for k in dd.keys():
        key = k.decode() if isinstance(k, bytes) else k
        if isinstance(dd[k], bytes):
            res[key] = dd[k].decode()
        else:
            res[key] = dd[k]
    return res


def dicts_val(path: str, data, **kwargs):
    """
    version: 1.0
    Get value from dictionary tree
    :param path: str (e.g. config.labels.cz\\.alps\\.mantra)
    :param data: dict tree
    :raise KeyError
    :return: Any - return value
    """
    delim = r'(?<!\\)\.' if 'delimiter' not in kwargs else kwargs['delimiter']
    try:
        dd = data
        for it in re.split(delim, path):
            key = it.replace('\\', '')
            if isinstance(dd, list) and key.isnumeric():
                key = int(key)
            dd = dd[key]
        return dd
    except Exception as ex:
        if 'default' in kwargs:
            return kwargs['default']
        raise ex


def cmd(*args, capture_output=True, ignore_error=False) -> subprocess.CompletedProcess:
    if os.getuid() != 0:
        args = ('sudo', *args)
    try:
        return subprocess.run(
            args, text=True, check=True, capture_output=capture_output
        )
    except subprocess.CalledProcessError as e:
        if not ignore_error:
            loggate.get_logger('cmd').error(
                e.stderr, meta={"cmd": ' '.join(args)}
            )
    return None


def get_wg_preshared_key() -> str:
    return subprocess.run(
        ('wg', 'genpsk'), capture_output=True, text=True, check=True
    ).stdout.strip()


def get_wg_private_key() -> str:
    return subprocess.run(
        ('wg', 'genkey'), capture_output=True, text=True, check=True
    ).stdout.strip()


def get_wg_public_key(private_key: str) -> str:
    return subprocess.run(
        ('wg', 'pubkey'), input=private_key,
        capture_output=True, text=True, check=True
    ).stdout.strip()


def ip_range_to_ips(ip_range: Optional[str]) -> List[IPv4Address]:
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


def optimalize_ip_range(ip_range) -> str:
    if not ip_range:
        return
    ips = ip_range_to_ips(ip_range)
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
    new_ips = ip_range_to_ips(new_range)
    diff = set(new_ips).difference(set(ips_copy))
    if diff:
        return ip_range
    if len(ip_range) < len(new_range):
        return new_range


def get_qrcode(content: str) -> io.BytesIO:
    qr = qrcode.make(content, image_factory=PyPNGImage)
    buffer = io.BytesIO()
    qr.save(buffer)
    buffer.seek(0)
    return buffer


def get_qrcode_based64(content: str) -> str:
    buffer = get_qrcode(content)
    qr_base64 = base64.b64encode(buffer.read()).decode('utf-8')
    return f"data:image/png;base64,{qr_base64}"
