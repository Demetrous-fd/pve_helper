from typing import Union, Any
from pathlib import Path

from pydantic import BaseSettings, conlist, validator


class Settings(BaseSettings):
    vk_token: str
    vk_admins: Union[int, conlist(int, min_items=1)]

    bastion_user: str = "root"
    bastion_host: str = "bastion.localhost"
    bastion_keys_path: str = "~/.ssh/authorized_keys"

    nginx_localdns: str = "10.0.0.1"
    nginx_localdomain: str = "local"
    nginx_domain: str = "localhost"

    pve_host: str = "pve.localhost"
    pve_user: str = "root@pam"
    pve_token_name: str = "token"
    pve_token: str
    pve_verify_ssl: bool = False
    pve_vm_default_password: str = "toor"
    pwd: Path = Path(__file__).parent.resolve()

    @validator("vk_admins")
    def validate_vk_admins(cls, value):
        if isinstance(value, int):
            return [value]
        return value

    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'

        @classmethod
        def parse_env_var(cls, field_name: str, raw_val: str) -> Any:
            if field_name == 'vk_admins':
                return [int(x) for x in raw_val.split(',')]
            return cls.json_loads(raw_val)


settings = Settings()
