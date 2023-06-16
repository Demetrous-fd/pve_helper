from string import digits, ascii_letters
from random import choice, randint
from enum import Enum
import json

from proxmoxer import ProxmoxAPI, core
from settings import settings

proxmox = ProxmoxAPI(
    host=settings.pve_host,
    user=settings.pve_user,
    token_name=settings.pve_token_name,
    token_value=settings.pve_token,
    verify_ssl=settings.pve_verify_ssl
)

pve = proxmox.nodes.get()[0]
pve_node = pve["node"]


# TODO: Это можно генерировать динамически
class VM(Enum):
    ubuntu_1g = ("ubuntu-22.04-1G.json", "Ubuntu server 22.04 1G RAM (Nginx, Docker/Docker-compose)")
    ubuntu_2g = ("ubuntu-22.04-2G.json", "Ubuntu server 22.04 2G RAM (Nginx, Docker/Docker-compose)")


def generate_password(length: int = 12) -> str:
    charset = digits + ascii_letters + "#*@" * 2
    return "".join([choice(charset) for _ in range(length)])


def user_exists(username: str) -> bool:
    userid = f"{username}@{pve_node}"
    try:
        proxmox.access.users(userid).get()
    except core.ResourceException:
        return False
    return True


def vm_with_domain_exists(domain: str) -> bool:
    domains = [lxc["name"] for lxc in proxmox.nodes(pve_node).lxc.get()]
    return True if domain in domains else False


def create_user(username: str, password: str = generate_password()) -> str:
    userid = f"{username}@{pve_node}"
    proxmox.access.users.post(userid=userid, password=password)
    return userid


def create_container(template: str, domain: str, ssh_key: str = None) -> int:
    get_vmid = lambda: randint(1000, 100000)
    config = {
        "node": pve_node,
        "vmid": get_vmid(),
        "nameserver": settings.nginx_localdns,
        "start": 1,
        "ssh-public-keys": ssh_key,
        "hostname": domain,
        "password": settings.pve_vm_default_password
    }
    with open(settings.pwd / "templates" / "lxc" / template) as file:
        template_config = json.load(file)

    while 1:
        try:
            proxmox.nodes(pve_node).lxc.post(
                **config, **template_config
            )
            break
        except core.ResourceException:
            config["vmid"] = get_vmid()

    return config["vmid"]


def grant_user_permission_to_vm(userid: str, vmid: int):
    proxmox.access.acl.put(users=userid, roles="PVEVMUser", path=f"/vms/{vmid}")


def run_new_user_task(
        user: str, password: str, domain: str,
        ssh_key: str, template: str = "ubuntu-22.04.json"
):
    user_id = create_user(user, password)
    vm_id = create_container(template, domain, ssh_key)
    grant_user_permission_to_vm(user_id, vm_id)

