import asyncio
import os

from datetime import datetime, timedelta
import sys

from aiogram import Router, types, F, Bot
from aiogram.types import Message
from aiogram.filters import Command, or_f
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from dotenv import load_dotenv

import app.database.orm_query as rq
from app.keyboards.reply import get_keyboard

from app.filters.check_admin import IsAdmin
from app.utils.helpers import clear_folder
from app.utils.account_manager import xlsx_accounts_parser

load_dotenv()

router = Router()
router.message.filter(IsAdmin())


BACK_TO_MENU = {"back_to_menu": "⬅️ Назад в меню"}
back = get_keyboard(BACK_TO_MENU["back_to_menu"])

ADMIN_MENU_KB_NAMES = {
    "accounts": "Аккаунти 🔑",
    "session": "Сесії 💻",
    "admin panel": "Адмін панель ⚙️",
}
admin_menu = get_keyboard(
    ADMIN_MENU_KB_NAMES["accounts"],
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
    "back_account_managment": '⬅️ Назад до меню "Аккаунти"',
}
account_managment = get_keyboard(
    ACCOUNT_MANAGMENT_KB_NAMES["account_list"],
    ACCOUNT_MANAGMENT_KB_NAMES["add_accounts"],
    ACCOUNT_MANAGMENT_KB_NAMES["remove_account"],
    BACK_TO_MENU["back_to_menu"],
    sizes=(1, 2, 1),
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
# @router.message(ACCOUNT_MANAGMENT_KB_NAMES["account_list"] == F.text)
# async def account_list(message: Message):
#     accounts rq.orm_add


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
        clear_folder(os.getenv("EXCEL_ACCOUNTS_FOLDER"))
        
        await bot.download_file(file_info.file_path, os.getenv("EXCEL_ACCOUNTS"))
        await message.reply(f"Файл отримано", reply_markup=account_managment)
        result = await xlsx_accounts_parser(os.getenv("EXCEL_ACCOUNTS"))
        
        if result:
            await message.reply(f"Добавлено аккаунтів: {result}", reply_markup=account_managment)
        else:
            await message.reply(f"Не додано жодного акаунту", reply_markup=account_managment)
        
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
