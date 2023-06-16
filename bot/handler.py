import logging
import string
import re

from vkbottle import Keyboard, KeyboardButtonColor, Text, VKAPIError
from pydantic import HttpUrl, parse_obj_as, ValidationError
from vkbottle.bot import Bot, Message
from vkbottle import BaseStateGroup

from bot.rules import AdminRule
from bot.storage import Storage
from settings import settings
import helper

# TODO: сделать отдельный процесс для letsencrypt и pve задач
# TODO: обновление ssh-ключей на сервере

bot = Bot(settings.vk_token)
bot.labeler.custom_rules["admin_access"] = AdminRule
storage = Storage()

logging.basicConfig(level=logging.INFO)

ALLOW_DOMAIN_CHAR = set(string.digits + string.ascii_lowercase + "-")

ADMIN_IDS = settings.vk_admins

GROUPS = ["И-19-1", "И-20-1", "И-21-1", "И-22-1", "И-22-2К", ]
GROUP_KEYBOARD = Keyboard(one_time=True)
GROUP_KEYBOARD.add(Text("И-19-1", {"group": "И-19-1"}))
GROUP_KEYBOARD.add(Text("И-20-1", {"group": "И-20-1"}))
GROUP_KEYBOARD.add(Text("И-21-1", {"group": "И-21-1"}))
GROUP_KEYBOARD.add(Text("И-22-1", {"group": "И-22-1"}))
GROUP_KEYBOARD.add(Text("И-22-2К", {"group": "И-22-2К"}))
GROUP_KEYBOARD = GROUP_KEYBOARD.get_json()


def get_vm_list_keyboard(user_id: int):
    keyboard = Keyboard(one_time=True)
    for template, name in helper.pve.VM._value2member_map_.keys():
        keyboard.add(Text(name[:40], {"vm": [template, name], "user_id": user_id}))
    return keyboard.get_json()


def get_inline_keyboard(user_id: int):
    inline_form_keyboard = Keyboard(inline=True)
    inline_form_keyboard.add(
        Text("Принять", {"id": user_id, "status": "OK"}), color=KeyboardButtonColor.POSITIVE
    )
    inline_form_keyboard.add(
        Text("Отказать", {"id": user_id, "status": "REJECT"}), color=KeyboardButtonColor.NEGATIVE
    )
    return inline_form_keyboard.get_json()


class State(BaseStateGroup):
    FIO = "fio"
    USERNAME = "username"
    GROUP = "group"
    SUBDOMAIN = "subdomain"
    SSH_KEY = "ssh_key"
    END_FORM = "end_form"
    ANY = "*"


class AnyValue:
    def __eq__(self, other):
        return True


@bot.on.message(regex=[re.compile(".*ачать"), re.compile(".*/start")])
async def start(message: Message):
    await message.answer("Привет, ответь на пару вопросов:")
    await bot.state_dispenser.set(message.peer_id, State.FIO)
    await message.answer("Введите ваше ФИО:")


@bot.on.message(state=State.FIO)
async def form_fio(message: Message):
    await bot.state_dispenser.set(message.peer_id, State.USERNAME)
    await storage.set(message.peer_id, {"fio": message.text})
    await message.answer("Придумай логин для входа в панель управления.")


@bot.on.message(state=State.USERNAME)
async def form_username(message: Message):
    if len(message.text) < 4:
        await message.answer("Придумайте логин большей длины.")
        return
    if len(message.text) > 32:
        await message.answer("Придумайте логин меньшей длины.")
        return
    if helper.pve.user_exists(message.text):
        await message.answer("Данный логин уже существует, придумайте другой.")
        return
    await bot.state_dispenser.set(message.peer_id, State.GROUP)
    await storage.set(message.peer_id, {"username": message.text})
    await message.answer("Из какой группы ?", keyboard=GROUP_KEYBOARD)


@bot.on.message(state=State.GROUP)
async def form_group(message: Message):
    await bot.state_dispenser.set(message.peer_id, State.SUBDOMAIN)
    await storage.set(message.peer_id, {"group": message.text})
    await message.answer(
        "Теперь введи название своего поддомена, максимальная длина 16 символов.\n\n"
        f"После создания ВМ, ваш сайт будут доступен по адресу <ваш поддомен>.{settings.nginx_domain}, "
        f"также вы сможете создавать свои поддомены <any>.<ваш поддомен>.{settings.nginx_domain}"
    )


@bot.on.message(state=State.SUBDOMAIN)
async def form_subdomain(message: Message):
    if not message.text:
        return

    subdomain = message.text.lower().split(".", 1)[0]
    try:
        parse_obj_as(HttpUrl, f"https://{subdomain}.{settings.nginx_domain}")
        if set(subdomain).difference(ALLOW_DOMAIN_CHAR):
            raise ValueError
    except (ValidationError, ValueError):
        await message.answer("Ваш поддомен содержит недопустимые символы, придумайте другой.")
        return

    if len(subdomain) < 2:
        await message.answer("Придумайте поддомен большей длины.")
        return

    if len(subdomain) > 16:
        await message.answer("Придумайте поддомен меньшей длины.")
        return

    if helper.pve.vm_with_domain_exists(subdomain):
        await message.answer("Данный поддомен уже существует, придумайте другой.")
        return

    await bot.state_dispenser.set(message.peer_id, State.SSH_KEY)
    await storage.set(message.peer_id, {"subdomain": subdomain})
    await message.answer(
        "Теперь отправь свой публичный ssh-ключ (содержимое файла: id_*.pub)\n"
        "Ключи от ssh находятся в папке пользователя, в проводнике нужно перейти по пути: %USERPROFILE%\\.ssh \n\n"
        "Если у тебя нет ssh-ключей, то создай их следуя шагам из этой статьи: "
        "https://vk.com/@-219467009-kak-ispolzovat-ssh?anchor=sozdanie-pary-klyuchey"
    )


@bot.on.message(state=State.SSH_KEY)
async def form_ssh_key(message: Message):

    if not helper.bastion.check_public_key(message.text):
        await message.answer("Невалидный публичный ssh-ключ, попробуйте пересоздать пару ssh-ключей")
        return

    await bot.state_dispenser.set(message.peer_id, State.ANY)
    await storage.set(message.peer_id, {"ssh-key": message.text})
    await message.answer(
        f"Спасибо, в ближайшее время рассмотрим ваш запрос и выдадим доступ."
    )
    form_data = (await storage.get(message.peer_id)).storage
    text = f"Пользователь: @id{message.peer_id}\n" \
           f"ФИО: {form_data['fio']}\n" \
           f"Ник: {form_data['username']}\n" \
           f"Группа: {form_data['group']}\n" \
           f"Поддомен: {form_data['subdomain']}\n" \
           f"SSH public key: {form_data['ssh-key']}"
    await bot.api.messages.send(
        peer_ids=ADMIN_IDS, random_id=0, message=text,
        keyboard=get_inline_keyboard(message.peer_id)
    )


@bot.on.message(admin_access=True, payload_contains={"status": "OK"})
async def ok_form(message: Message):
    payload = message.get_payload_json()
    user = payload['id']
    await message.answer(f"Выбор ВМ для пользователя: @id{user}", keyboard=get_vm_list_keyboard(user))


@bot.on.message(admin_access=True, payload_contains={"status": "REJECT"})
async def reject_form(message: Message):
    payload = message.get_payload_json()
    await bot.state_dispenser.delete(payload["id"])
    await bot.api.messages.send(
        peer_id=payload["id"], random_id=0,
        message="Грустно, но вы получили отказ 😔"
    )


@bot.on.message(admin_access=True, payload_contains={"vm": AnyValue()})
async def create_user_vm(message: Message):
    payload = message.get_payload_json()
    vm = payload.get("vm", ("ubuntu-22.04-1G.json", "Ubuntu server 22.04 1G RAM"))
    user_id = payload.get("user_id", 0)
    if user_id == 0:
        return

    await bot.api.messages.send(
        peer_id=user_id, random_id=0, message="Wait 🌚"
    )
    form_data = (await storage.get(user_id)).storage
    password = helper.pve.generate_password()
    helper.pve.run_new_user_task(
        user=form_data["username"],
        password=password,
        domain=form_data["subdomain"],
        ssh_key=form_data["ssh-key"],
        template=vm[0]
    )
    helper.bastion.load_public_key(form_data["ssh-key"])
    helper.nginx.run_new_user_task(form_data["subdomain"], "apt")
    text = f"Вам выдана VM: {vm[1]}\n" \
           f"Логин: root\n" \
           f"Пароль: {settings.pve_vm_default_password}\n" \
           f"Ваш поддомен: https://{form_data['subdomain']}.{settings.nginx_domain}\n\n" \
           f"Панель управления: https://space.{settings.nginx_domain}\n" \
           f"Логин: {form_data['username']}\n" \
           f"Пароль: {password}\n\n" \
           "SSH jump-сервер:\n" \
           f"Адрес: {settings.nginx_domain}\n" \
           "User: jump\n\n" \
           "SSH ваш-сервер:\n" \
           f"Адрес: {form_data['subdomain']}.{settings.nginx_localdomain}\n" \
           "User: root\n\n" \
           "Команда для быстрого доступ к VM через ssh:\n" \
           f"\tssh -J jump@{settings.nginx_domain} root@{form_data['subdomain']}.{settings.nginx_localdomain}\n\n"
    await bot.api.messages.send(
        peer_id=user_id, random_id=0,
        message=text
    )
    await bot.api.messages.send(
        peer_ids=ADMIN_IDS, random_id=0, message=f"Пользователю: {user_id} выданы данные"
    )


@bot.error_handler.register_error_handler(Exception)
async def runtime_error_handler(e: Exception):
    logging.error("возникла ошибка runtime", e)
    try:
        await bot.api.messages.send(
            peer_ids=ADMIN_IDS, random_id=0,
            message=f"возникла ошибка: {e}"
        )
    except VKAPIError:
        pass
