from pathlib import Path
import subprocess

import jinja2

from settings import settings

env = jinja2.Environment(loader=jinja2.FileSystemLoader(settings.pwd / "templates" / "nginx"))

NGINX_PATH = Path("/etc/nginx")
SITES_AVAILABLE = NGINX_PATH / "sites-available"
SITES_ENABLED = NGINX_PATH / "sites-enabled"


def render_nginx_config(subdomain: str, vm_ip: str, domain: str) -> str:
    template = env.get_template("nginx-config.conf")
    return template.render(subdomain=subdomain, vm_ip=vm_ip, domain=domain, dns=settings.nginx_localdns)


def create_config(subdomain: str, vm_domain: str, local_domain: str, domain: str):
    config = render_nginx_config(subdomain, f"{vm_domain}.{local_domain}", domain)
    path = SITES_AVAILABLE / f"{vm_domain}.{local_domain}.conf"
    with open(path, "w", encoding="utf8") as file:
        file.write(config)


def create_letsencrypt_certificate(subdomain: str):
    command = "certbot certonly --dns-cloudflare --dns-cloudflare-credentials " \
              f"/root/.secrets/cloudflare.ini -d *.{subdomain}.{settings.nginx_domain}" \
              f" --preferred-challenges dns-01 && ping -c 42 {settings.nginx_localdns} > /dev/null && nginx -s reload"
    subprocess.Popen(command, shell=True,
                     stdin=None, stdout=None, stderr=None, close_fds=True)


def enable_config(vm_domain: str, local_domain: str):
    config_name = f"{vm_domain}.{local_domain}.conf"
    path = SITES_ENABLED / config_name
    path.symlink_to(SITES_AVAILABLE / config_name)


def disable_config(vm_domain: str):
    path = SITES_ENABLED / f"{vm_domain}.conf"
    path.unlink()


def reload_nginx():
    code, result = subprocess.getstatusoutput("nginx -t")
    if code == 0:
        subprocess.call(["nginx", "-s", "reload"])
    else:
        print(code, result)


def run_new_user_task(domain: str, pve_local_domain: str = settings.nginx_localdomain):
    create_letsencrypt_certificate(domain)
    create_config(domain, domain, pve_local_domain, settings.nginx_domain)
    enable_config(domain, pve_local_domain)
    reload_nginx()
