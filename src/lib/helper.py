import hashlib
import os
import re
import subprocess
import loggate
import yaml



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


def get_wg_private_key() -> str:
    return subprocess.run(
        ('wg', 'genkey'), capture_output=True, text=True, check=True
    ).stdout.strip()


def get_wg_public_key(private_key: str) -> str:
    return subprocess.run(
        ('wg', 'pubkey'), input=private_key,
        capture_output=True, text=True, check=True
    ).stdout.strip()
