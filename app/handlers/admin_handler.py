import asyncio
import os

from datetime import datetime, timedelta
import sys

from aiogram import Router, types, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, or_f
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from dotenv import load_dotenv

from app.bots.auth import TelegramLogin
import app.database.orm_query as rq
from app.keyboards.reply import get_keyboard
from app.keyboards.inline import get_callback_btns

from app.filters.check_admin import IsAdmin
from app.utils.get_account_app_data import auth_proccess
from app.utils.helpers import clear_folder
from app.utils.account_manager import xlsx_accounts_parser
from app.utils.get_account_app_data import auth_proccess

load_dotenv()

router = Router()
router.message.filter(IsAdmin())


BACK_TO_MENU = {"back_to_menu": "⬅️ Назад в меню"}
back = get_keyboard(BACK_TO_MENU["back_to_menu"])

ADMIN_MENU_KB_NAMES = {
    "accounts": "Аккаунти 🔑",
    "proxy": "Проксі 🌐",
    "session": "Сесії 💻",
    "admin panel": "Адмін панель ⚙️",
}
admin_menu = get_keyboard(
    ADMIN_MENU_KB_NAMES["accounts"],
    ADMIN_MENU_KB_NAMES["proxy"],
    ADMIN_MENU_KB_NAMES["session"],
    ADMIN_MENU_KB_NAMES["admin panel"],
)

ADMIN_MANAGMENT_KB_NAMES = {
    "add_admin": "Добавити адміністратора ➕",
    "remove_admin": "Видалити адміністратора 🗑️",
    "admin_list": "Список адміністраторів 👥",
    "back_admin_managment": "⬅️ Повернутись в адмін панель",
}
admin_managment = get_keyboard(
    ADMIN_MANAGMENT_KB_NAMES["admin_list"],
    ADMIN_MANAGMENT_KB_NAMES["add_admin"],
    ADMIN_MANAGMENT_KB_NAMES["remove_admin"],
    BACK_TO_MENU["back_to_menu"],
    sizes=(1, 2, 1),
)
back_admin_managment = get_keyboard(ADMIN_MANAGMENT_KB_NAMES["back_admin_managment"])


# admin /admin
@router.message(
    or_f(
        Command("admin"),
        (BACK_TO_MENU["back_to_menu"] == F.text),
    )
)
async def cmd_admin(message: Message, state: FSMContext):
    await message.answer("Головне меню 📋", reply_markup=admin_menu)
    await state.clear()


class AdminManagment(StatesGroup):
    add_admin = State()
    remove_admin = State()


# admin panel
@router.message(
    or_f(
        (ADMIN_MENU_KB_NAMES["admin panel"] == F.text),
        (ADMIN_MANAGMENT_KB_NAMES["back_admin_managment"] == F.text),
    )
)
async def cmd_admin_panel(message: Message, state: FSMContext):
    await message.answer('Розділ "Адмін панель ⚙️"', reply_markup=admin_managment)
    await state.clear()


# admin list
@router.message(ADMIN_MANAGMENT_KB_NAMES["admin_list"] == F.text)
async def cmd_admin_panel(message: Message):
    admins = await rq.orm_get_all_admins()
    admins_str = "Список адміністраторів 🤖\n"

    for admin in admins:
        admins_str += f"@{admin.name if admin.name else admin.tg_id}\n"

    await message.answer(admins_str, reply_markup=admin_managment)


# admin add
@router.message(ADMIN_MANAGMENT_KB_NAMES["add_admin"] == F.text)
async def add_admin_first(message: Message, state: FSMContext):
    await message.answer(
        "Введіть юзернейм адміністратора, приклад:\n@andy12, @pocoX3, @tramp55",
        reply_markup=back_admin_managment,
    )
    await state.set_state(AdminManagment.add_admin)


@router.message(AdminManagment.add_admin)
async def add_admin_second(message: Message, state: FSMContext):
    await state.update_data(username=message.text)
    username = (await state.get_data()).get("username")

    if username[0] == "@":
        username = username[1:]

        if await rq.orm_get_user(value=username, get_by="name"):
            result = await rq.orm_add_admin(username)

            if result:
                await message.answer(
                    f"Адміністратор @{username} успішно доданий ✅",
                    reply_markup=admin_managment,
                )
            else:
                await message.answer(
                    f"@{username} має права адміністратора",
                    reply_markup=admin_managment,
                )
        else:
            await message.answer(
                f"@{username} не має в базі.", reply_markup=admin_managment
            )
    else:
        await message.answer(
            "Ви ввели некоректний юзернейм, спробуйте знову.",
            reply_markup=admin_managment,
        )

    await state.clear()


# admin remove
@router.message(ADMIN_MANAGMENT_KB_NAMES["remove_admin"] == F.text)
async def remove_admin_first(message: Message, state: FSMContext):
    await message.answer(
        "Введіть юзернейм адміністратора, приклад:\n@andy12, @pocoX3, @tramp55",
        reply_markup=back_admin_managment,
    )
    await state.set_state(AdminManagment.remove_admin)


@router.message(AdminManagment.remove_admin)
async def remove_admin_second(message: Message, state: FSMContext):
    await state.update_data(username=message.text)
    username = (await state.get_data()).get("username")

    if username[0] == "@":
        username = username[1:]

        if username == message.from_user.username:
            await message.answer(
                "Ви не можете забрати в себе права!", reply_markup=admin_managment
            )
            await state.clear()
            return

        admin = await rq.orm_get_user(value=username, get_by="name")

        if admin:
            if admin.is_admin:
                await rq.orm_remove_admin(username)
                await message.answer(
                    f"Адміністратор @{username} успішно видалений ✅",
                    reply_markup=admin_managment,
                )
            else:
                await message.answer(
                    f"@{username} не має прав адміністратора",
                    reply_markup=admin_managment,
                )
        else:
            await message.answer(
                f"@{username} не має в базі.", reply_markup=admin_managment
            )
    else:
        await message.answer(
            "Ви ввели некоректний юзернейм, спробуйте знову.",
            reply_markup=admin_managment,
        )

    await state.clear()


# account panel
ACCOUNT_MANAGMENT_KB_NAMES = {
    "account_list": "Список аккаунтів 📃",
    "add_accounts": "Добавити аккаунти 📲",
    "remove_account": "Видалити аккаунти 🗑️",
    "api_auth_proccess": "Авторизація API ⚙",
    "telegram_auth_proccess": "Авторизація Telegram 🚀",
    "back_account_managment": '⬅️ Назад до меню "Аккаунти"',
}
account_managment = get_keyboard(
    ACCOUNT_MANAGMENT_KB_NAMES["account_list"],
    ACCOUNT_MANAGMENT_KB_NAMES["add_accounts"],
    ACCOUNT_MANAGMENT_KB_NAMES["remove_account"],
    ACCOUNT_MANAGMENT_KB_NAMES["api_auth_proccess"],
    ACCOUNT_MANAGMENT_KB_NAMES["telegram_auth_proccess"],
    BACK_TO_MENU["back_to_menu"],
    sizes=(1, 2, 2, 1),
)
back_account_managment = get_keyboard(
    ACCOUNT_MANAGMENT_KB_NAMES["back_account_managment"]
)


class AccountState(StatesGroup):
    add_accounts = State()
    remove_accounts = State()


@router.message(
    or_f(
        (ADMIN_MENU_KB_NAMES["accounts"] == F.text),
        (ACCOUNT_MANAGMENT_KB_NAMES["back_account_managment"] == F.text),
    )
)
async def account_panel(message: Message, state: FSMContext):
    await message.answer('Розділ "Аккаунти 🔑"', reply_markup=account_managment)
    await state.clear()


# account list
@router.message(ACCOUNT_MANAGMENT_KB_NAMES["account_list"] == F.text)
async def account_list(message: Message):
    accounts = await rq.orm_get_all_accounts()

    await message.answer("Список аккаунтів 👇", reply_markup=account_managment)

    for account in accounts:
        text = f"Номер: <code>{account.number}</code>\n"
        text += f"Додаток створений: {'✅' if account.is_app_created else '❌'}\n"
        if account.is_app_created:
            text += f"API ID: <code>{account.api_id}</code>\n"
            text += f"API HASH: <code>{account.api_hash}</code>\n"
            text += f"Сесія створена: {'✅' if account.is_session_created else '❌'}\n"
            if account.is_session_created:
                text += f"ID сесіі: {account.session_id}\n"

        await message.answer(text)


# add accounts
@router.message(ACCOUNT_MANAGMENT_KB_NAMES["add_accounts"] == F.text)
async def add_account_first(message: Message, state: FSMContext):
    await message.answer(
        "Надішліть базу номерів у форматі .xlsx",
        reply_markup=back_account_managment,
    )
    await state.set_state(AccountState.add_accounts)


@router.message(AccountState.add_accounts)
async def add_account_second(message: Message, state: FSMContext, bot: Bot):
    await state.update_data(file_name=message.document)
    data = await state.get_data()
    document = data.get("file_name")

    if document is None:
        await message.reply(
            "Будь ласка, надішліть правильний файл.",
            reply_markup=account_managment,
        )
        await state.clear()
        return

    # If document is lxml create async task for ChatJoiner
    if (
        document.mime_type
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ):
        file_info = await bot.get_file(document.file_id)
        clear_folder(os.getenv("EXCEL_FOLDER"))

        await bot.download_file(file_info.file_path, os.getenv("EXCEL_ACCOUNTS"))
        await message.reply(f"Файл отримано")
        result = await xlsx_accounts_parser(os.getenv("EXCEL_ACCOUNTS"))

        if result:
            await message.reply(
                f"Добавлено аккаунтів: {result}", reply_markup=account_managment
            )
        else:
            await message.reply(
                f"Не додано жодного акаунту", reply_markup=account_managment
            )

    else:
        await message.reply(
            "Будь ласка, надішліть Excel файл у форматі .xlsx",
            reply_markup=account_managment,
        )
    await state.clear()


# remove accounts
@router.message(ACCOUNT_MANAGMENT_KB_NAMES["remove_account"] == F.text)
async def remove_account(message: Message, state: FSMContext):
    await message.answer("Введіть номер:", reply_markup=back_account_managment)
    await state.set_state(AccountState.remove_accounts)


@router.message(AccountState.remove_accounts)
async def remove_account_second(message: Message, state: FSMContext):
    await state.update_data(number=message.text)
    data = await state.get_data()
    number = data.get("number")

    if number is None:
        await message.reply(
            "Будь ласка, надішліть правильний номер.",
            reply_markup=account_managment,
        )
        await state.clear()
        return

    check = await rq.orm_get_account(number)

    if check:
        await rq.orm_remove_account(number)
        await message.reply(
            f"Аккаунт <code>{number}</code> успішно видалений",
            reply_markup=account_managment,
        )
    else:
        await message.reply(
            f"Аккаунт <code>{number}</code> не знайдено.",
            reply_markup=account_managment,
        )

    await state.clear()


# api auth
@router.message(ACCOUNT_MANAGMENT_KB_NAMES["api_auth_proccess"] == F.text)
async def api_auth(message: Message, state: FSMContext):
    await message.answer(
        "Розпочинаю API авторизацію...", reply_markup=back_account_managment
    )


class Auth(StatesGroup):
    code = State()


login_manager = TelegramLogin()


# telegram auth
@router.message(ACCOUNT_MANAGMENT_KB_NAMES["telegram_auth_proccess"] == F.text)
async def api_auth(message: Message):
    btns = {"Так": "start_auth_tg_yes", "Ні": "start_auth_tg_no"}
    await message.answer(
        f'Розділ "{ACCOUNT_MANAGMENT_KB_NAMES["telegram_auth_proccess"]}"',
        reply_markup=back_account_managment,
    )
    await message.answer(
        "Запутити процес авторизації?", reply_markup=get_callback_btns(btns=btns)
    )


@router.callback_query(F.data == "start_auth_tg_yes")
async def start_auth_tg_yes(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text("Розпочинаю Telegram авторизацію...")

    await login_manager.start_login(callback.message, state)
    await state.set_state(Auth.code)


@router.callback_query(F.data == "start_auth_tg_no")
async def start_auth_tg_no(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text("Дію скасовано")
    await callback.message.answer("Повертаюсь назад...", reply_markup=account_managment)


@router.message(Auth.code)
async def code_handler(message: types.Message, state: FSMContext):
    if message.text and message.text.isdigit():
        code_text = message.text

        # Завершуємо авторизацію поточного акаунта та переходимо до наступного
        await login_manager.finish_login(message, code_text)

        # Очищаємо стан, щоб дозволити подальші команди
        await state.clear()
    else:
        await message.answer("Будь ласка, введи коректний код підтвердження.")


# ---------- PROXY ----------

# proxy panel
PROXY_MANAGMENT_KB_NAMES = {
    "proxy_list": "Список проксі 📃",
    "add_proxy": "Добавити проксі 📲",
    "remove_proxy": "Видалити проксі 🗑️",
    "back_proxy_managment": '⬅️ Назад до меню "Проксі"',
}
proxy_managment = get_keyboard(
    PROXY_MANAGMENT_KB_NAMES["proxy_list"],
    PROXY_MANAGMENT_KB_NAMES["add_proxy"],
    PROXY_MANAGMENT_KB_NAMES["remove_proxy"],
    BACK_TO_MENU["back_to_menu"],
    sizes=(1, 2, 1),
)
back_account_managment = get_keyboard(
    ACCOUNT_MANAGMENT_KB_NAMES["back_account_managment"]
)


class ProxyState(StatesGroup):
    add_proxies = State()
    remove_proxies = State()


# proxy menu
@router.message(
    or_f(
        (ADMIN_MENU_KB_NAMES["proxy"] == F.text),
        (PROXY_MANAGMENT_KB_NAMES["back_proxy_managment"] == F.text),
    )
)
async def proxy(message: Message, state: FSMContext):
    await message.answer(
        f'Розділ "{ADMIN_MENU_KB_NAMES["proxy"]}"', reply_markup=proxy_managment
    )
    await state.clear()


# proxy add
@router.message(PROXY_MANAGMENT_KB_NAMES["add_proxy"] == F.text)
async def add_proxy_first(message: Message, state: FSMContext):
    await message.answer(
        "Надішліть базу проксі у форматі .xlsx",
        reply_markup=back_account_managment,
    )
    await state.set_state(ProxyState.add_proxies)


@router.message(ProxyState.add_proxies)
async def add_proxy_second(message: Message, state: FSMContext, bot: Bot):
    await state.update_data(file_name=message.document)
    data = await state.get_data()
    document = data.get("file_name")

    if document is None:
        await message.reply(
            "Будь ласка, надішліть правильний файл.",
            reply_markup=account_managment,
        )
        await state.clear()
        return

    # If document is lxml create async task for ChatJoiner
    if (
        document.mime_type
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ):
        file_info = await bot.get_file(document.file_id)
        clear_folder(os.getenv("EXCEL_FOLDER"))

        await bot.download_file(file_info.file_path, os.getenv("EXCEL_PROXIES"))
        await message.reply(f"Файл отримано")
        result = await xlsx_accounts_parser(os.getenv("EXCEL_PROXIES"))

        if result:
            await message.reply(
                f"Добавлено аккаунтів: {result}", reply_markup=account_managment
            )
        else:
            await message.reply(
                f"Не додано жодного акаунту", reply_markup=account_managment
            )

    else:
        await message.reply(
            "Будь ласка, надішліть Excel файл у форматі .xlsx",
            reply_markup=account_managment,
        )
    await state.clear()


# session panel
# SESSION_MANAGMENT_KB_NAMES = {
#     "add_session": "Добавити сесію ✒",
#     "remove_session": "Видалити сесію 🗑️",
#     "session_list": "Список сесій 📃",
#     "back_session_managment": "⬅️ Назад до панелі сесій",
# }
# session_managment = get_keyboard(
#     SESSION_MANAGMENT_KB_NAMES["session_list"],
#     SESSION_MANAGMENT_KB_NAMES["add_session"],
#     SESSION_MANAGMENT_KB_NAMES["remove_session"],
#     BACK_TO_MENU["back_to_menu"],
#     sizes=(1, 2, 1),
# )
# back_session_managment = get_keyboard(
#     SESSION_MANAGMENT_KB_NAMES["back_session_managment"]
# )

# # session panel
# @router.message(
#     or_f(
#         (ADMIN_MENU_KB_NAMES["session"] == F.text),
#         (SESSION_MANAGMENT_KB_NAMES["back_session_managment"] == F.text),
#     )
# )
# async def session_panel(message: Message, state: FSMContext):
#     await message.answer('Розділ "Сесії 💻"', reply_markup=session_managment)
#     await state.clear()
