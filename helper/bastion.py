from typing import Optional
import subprocess
import random

import paramiko

from settings import settings

BASTION_USER = settings.bastion_user
BASTION_HOST = settings.bastion_host
BASTION_KEYS_PATH = settings.bastion_keys_path


def mixin_client(func):
    def wrapper(*args, **kwargs):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(hostname=BASTION_HOST, username=BASTION_USER)

        result = func(*args, client=client, **kwargs)
        client.close()
        return result
    return wrapper


@mixin_client
def get_public_keys(client) -> bytes:
    _, stdout, _ = client.exec_command(f"cat {BASTION_KEYS_PATH}")
    return stdout.read()


@mixin_client
def load_public_key(ssh_key: str, client) -> Optional[bytes]:
    keys = get_public_keys()
    if not ssh_key.encode() in keys:
        _, stdout, _ = client.exec_command(f"echo '{ssh_key}' >> {BASTION_KEYS_PATH}")
        return stdout.read()
    return None


@mixin_client
def remove_public_key(ssh_key: str, client) -> bytes:
    keys = get_public_keys().decode()
    keys = keys.replace(ssh_key, "")
    command = f"echo '{keys}' > {BASTION_KEYS_PATH}"
    _, stdout, _ = client.exec_command(command)
    return stdout.read()


def check_public_key(ssh_key: str) -> bool:
    filename = f"pubkey_{random.randint(0, 1000000)}.pub"
    command = f'mkdir -p /tmp/bastion && echo {ssh_key} >> /tmp/bastion/{filename} && ssh-keygen -l -f /tmp/bastion/{filename}'
    result = subprocess.getstatusoutput(command)
    return True if result[0] == 0 else False
