from typing import Union

from vkbottle.bot import Message
from vkbottle import ABCRule

from settings import settings


class AdminRule(ABCRule[Message]):
    def __init__(self, enable: bool = False):
        self.enable = enable

    async def check(self, event: Message) -> Union[dict, bool]:
        if self.enable is False:
            return True
        return event.peer_id in settings.vk_admins
