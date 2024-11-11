import ast
import asyncio
import os
import openai

from datetime import datetime, timedelta

from io import BytesIO
from aiogram import Router, types, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command, or_f, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from dotenv import load_dotenv
import validators

import app.database.orm_query as rq

from app.bots.auth import TelegramLogin
from app.keyboards.reply import get_keyboard
from app.keyboards.inline import get_callback_btns

from app.filters.check_admin import IsAdmin
from app.bots.get_account_app_data import AuthTgAPI
from app.utils.helpers import clear_folder, generate_dialogs, roles_distribution
from app.utils.account_manager import xlsx_accounts_parser, xlsx_proxies_parser

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
    "api_auth_proccess": "Авторизація API ⚙",
    "telegram_auth_proccess": "Авторизація Telegram 🚀",
    "set_proxy": "Встановити проксі 🌐",
    "back_account_managment": '⬅️ Назад до меню "Аккаунти"',
}
account_managment = get_keyboard(
    ACCOUNT_MANAGMENT_KB_NAMES["account_list"],
    ACCOUNT_MANAGMENT_KB_NAMES["add_accounts"],
    ACCOUNT_MANAGMENT_KB_NAMES["remove_account"],
    ACCOUNT_MANAGMENT_KB_NAMES["api_auth_proccess"],
    ACCOUNT_MANAGMENT_KB_NAMES["telegram_auth_proccess"],
    ACCOUNT_MANAGMENT_KB_NAMES["set_proxy"],
    BACK_TO_MENU["back_to_menu"],
    sizes=(1, 2, 2, 1, 1),
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
    global auth_task, api_auth_task

    if auth_task and not auth_task.done():
        auth_task.cancel()
        try:
            await auth_task
        except asyncio.CancelledError:
            await message.answer("Телеграм авторизація була скасована.")

    if api_auth_task and not api_auth_task.done():
        api_auth_task.cancel()
        try:
            await api_auth_task
        except asyncio.CancelledError:
            await message.answer("API авторизація була скасована.")

    await message.answer('Розділ "Аккаунти 🔑"', reply_markup=account_managment)
    await state.clear()


# account list
@router.message(ACCOUNT_MANAGMENT_KB_NAMES["account_list"] == F.text)
async def account_list(message: Message):
    accounts = await rq.orm_get_all_accounts()

    await message.answer("Список аккаунтів 👇", reply_markup=account_managment)

    if not accounts:
        await message.answer("Список аккаунтів порожній")
        return

    for account in accounts:
        text = f"Номер: <code>{account.number}</code>\n"
        text += f"Проксі: <code>{account.proxy}</code>\n"
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


# ---------- TG AUTH ----------
class Auth(StatesGroup):
    code = State()


login_manager = TelegramLogin()
auth_task = None


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
    global auth_task

    await callback.answer()
    await callback.message.edit_text("Розпочинаю Telegram авторизацію...")

    # await login_manager.start_login(callback.message, state)
    auth_task = asyncio.create_task(login_manager.start_login(callback.message))
    await state.set_state(Auth.code)


@router.callback_query(F.data == "start_auth_tg_no")
async def start_auth_tg_no(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text("Дію скасовано")
    await callback.message.answer("Повертаюсь назад...", reply_markup=account_managment)


@router.message(Auth.code)
async def code_handler(message: types.Message, state: FSMContext):
    if message.text and message.text.isdigit():
        global auth_task

        code_text = message.text
        auth_task = await login_manager.finish_login(message, code_text)

        await state.clear()
    else:
        await message.answer("Будь ласка, введи коректний код підтвердження.")


# ---------- SET ACCOUNT PROXY ----------
SET_ACCOUNT_PROXY_KB_NAMES = {
    "add_proxy": "Встановити проксі 📲",
    "remove_proxy": "Видалити проксі 🗑️",
    "back_set_account_proxy": '⬅️ Назад до меню "Встановити проксі"',
}
set_account_proxy_menu = get_keyboard(
    SET_ACCOUNT_PROXY_KB_NAMES["add_proxy"],
    SET_ACCOUNT_PROXY_KB_NAMES["remove_proxy"],
    ACCOUNT_MANAGMENT_KB_NAMES["back_account_managment"],
    sizes=(2, 1),
)
back_to_set_account_proxy = get_keyboard(
    SET_ACCOUNT_PROXY_KB_NAMES["back_set_account_proxy"]
)


@router.message(ACCOUNT_MANAGMENT_KB_NAMES["set_proxy"] == F.text)
async def set_account_proxy(message: Message, state: FSMContext):
    await message.answer(
        "Ви переходите до меню 'Встановити проксі'", reply_markup=set_account_proxy_menu
    )
    await state.clear()


@router.message(SET_ACCOUNT_PROXY_KB_NAMES["add_proxy"] == F.text)
async def add_proxy(message: Message, state: FSMContext):
    for account in await rq.orm_get_specific_accounts():
        ...
    await message.answer("Введіть проксі", reply_markup=back_to_set_account_proxy)


@router.message(SET_ACCOUNT_PROXY_KB_NAMES["remove_proxy"] == F.text)
async def remove_proxy(message: Message, state: FSMContext):
    await message.answer("Введіть проксі", reply_markup=back_to_set_account_proxy)


# ---------- API AUTH ----------
class APIAuth(StatesGroup):
    auth_status = State()
    code = State()


api_login_manager = None
api_auth_task = None


# api auth panel
@router.message(ACCOUNT_MANAGMENT_KB_NAMES["api_auth_proccess"] == F.text)
async def api_auth(message: Message):
    btns = {"Так": "start_api_auth_tg_yes", "Ні": "start_api_auth_tg_no"}
    await message.answer(
        f'Розділ "{ACCOUNT_MANAGMENT_KB_NAMES["api_auth_proccess"]}"',
        reply_markup=back_account_managment,
    )
    await message.answer(
        "Запутити процес авторизації API?", reply_markup=get_callback_btns(btns=btns)
    )


@router.callback_query(F.data == "start_api_auth_tg_yes")
async def start_auth_tg_yes(callback: CallbackQuery, state: FSMContext):
    global api_auth_task, api_login_manager

    await callback.answer()
    await callback.message.edit_text("Розпочинаю Telegram API авторизацію...")

    if api_auth_task and not api_auth_task.done():
        api_auth_task.cancel()

    if not api_login_manager:
        api_login_manager = None

    api_login_manager = AuthTgAPI(account_managment)
    # await api_login_manager.start_login(callback.message)
    api_auth_task = asyncio.create_task(api_login_manager.start_login(callback.message))

    await state.set_state(APIAuth.auth_status)


@router.callback_query(F.data == "start_api_auth_tg_no")
async def start_auth_tg_no(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text("Дію скасовано")
    await callback.message.answer("Повертаюсь назад...", reply_markup=account_managment)


@router.message(APIAuth.auth_status)
async def api_auth_handler(message: Message, state: FSMContext):
    global api_login_manager

    print("!" * 10, api_login_manager)
    await api_login_manager.first_step(message)
    await state.set_state(APIAuth.code)


@router.message(APIAuth.code)
async def code_handler(message: types.Message, state: FSMContext):
    global api_auth_task, api_login_manager

    code_text = message.text
    api_auth_task = await api_login_manager.second_step(message, code_text)

    await state.set_state(APIAuth.auth_status)


# ---------- SESSION ----------
# session panel
SESSION_MANAGMENT_KB_NAMES = {
    "add_session": "Добавити сесію 💻",
    "remove_session": "Видалити сесію 🗑️",
    "session_list": "Список сесій 📕",
    'step_back': 'Назад',
    "back_session_managment": "⬅️ Назад до панелі сесій",
}
session_managment = get_keyboard(
    SESSION_MANAGMENT_KB_NAMES["session_list"],
    SESSION_MANAGMENT_KB_NAMES["add_session"],
    SESSION_MANAGMENT_KB_NAMES["remove_session"],
    BACK_TO_MENU["back_to_menu"],
    sizes=(1, 2, 1),
)
back_session_managment = get_keyboard(
    SESSION_MANAGMENT_KB_NAMES["back_session_managment"]
)


class SessionState(StatesGroup):
    session_type = State()
    prompt = State()
    account_count = State()
    chat_url = State()
    answer_time = State()

    remove_session = State()


# session panel
@router.message(
    or_f(
        (ADMIN_MENU_KB_NAMES["session"] == F.text),
        (SESSION_MANAGMENT_KB_NAMES["back_session_managment"] == F.text),
    )
)
async def session_panel(message: Message, state: FSMContext):
    await message.answer('Розділ "Сесії 💻"', reply_markup=session_managment)
    await state.clear()


# add session
@router.message(SESSION_MANAGMENT_KB_NAMES["add_session"] == F.text)
async def add_session_first(message: Message, state: FSMContext):
    await message.answer("Введіть назву сесії 👇", reply_markup=back_session_managment)
    await state.set_state(SessionState.session_type)


@router.message(SessionState.session_type)
async def add_session_second(message: Message, state: FSMContext):
    await state.update_data(session_type=message.text)
    await message.answer("Введіть промпт 👇", reply_markup=back_session_managment)
    await state.set_state(SessionState.prompt)

@router.message(SessionState.prompt)
async def add_session_third(message: Message, state: FSMContext):
    prompt = message.text
    
    result = await generate_dialogs(prompt, message, back_session_managment)
    await state.update_data(data_json=result)

@router.callback_query(F.data == "use_dialog")
async def use_dialog(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text("Діалог підтверджено")

    await callback.message.answer(
        "Введіть посилання на чат 👇", reply_markup=back_session_managment
    )

    await state.set_state(SessionState.chat_url)


@router.callback_query(F.data == "dont_use_dialog")
async def dont_use_dialog(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text("Діалог скасовано")
    await add_session_second(callback.message, state)


@router.message(SessionState.chat_url)
async def add_session_fourth(message: Message, state: FSMContext):
    url = message.text

    if validators.url(url):
        await message.answer("Юрл підійшов", reply_markup=back_session_managment)
        await state.update_data(chat_url=message.text)
        
        await message.answer('Введіть проміжок часу між відповідями користувачів (секунди)\nПриклад: 60-120, 35-60, 20-30', reply_markup=back_session_managment)
        await state.set_state(SessionState.answer_time)
    else:
        await message.answer("Юрл не валідний", reply_markup=back_session_managment)
        return

@router.message(SessionState.answer_time)
async def add_session_fifth(message: Message, state: FSMContext):
    answer_time = message.text.split('-')
    
    if int(answer_time[0]) <= int(answer_time[1]):
        await message.answer("Введіть правильний проміжок часу між відповідями користувачів", reply_markup=back_session_managment)
    await state.update_data(answer_time=message.text)
    data_str = await state.get_value('data_json')
    data_json = ast.literal_eval(data_str)
    
    print('!' * 10, type(data_json))
    
    unique_users = [message['user_id'] for message in data_json]
    
    await message.answer('Починаю розприділяти ролі між аккаунтами', reply_markup=back_session_managment)
    accounts = await rq.orm_get_specific_accounts(is_session_created=True)
    account_list = []


    if accounts:
        for account in accounts:
            if not account.is_active:
                account_list.append(account)
    
    if len(account_list) < len(unique_users):
        await message.answer('Недостатньо вільних аккаунтів! Спочатку авторизуйте аккаунти', reply_markup=session_managment)
        await state.clear()
        return
    
    await roles_distribution()

@router.message(StateFilter('*'), F.text.casefold() == "отмена")
async def cancel_handler(message: types.Message, state: FSMContext) -> None:

    current_state = await state.get_state()
    if current_state is None:
        return

    await state.clear()
    await message.answer("Действия отменены", reply_markup=session_managment)

@router.message(StateFilter('*'), F.text.casefold() == "назад")
async def back_step_handler(message: types.Message, state: FSMContext) -> None:

    current_state = await state.get_state()

    if current_state == SessionState.name:
        await message.answer('Предидущего шага нет, или введите название товара или напишите "отмена"')
        return

    previous = None
    for step in SessionState.__all_states__:
        if step.state == current_state:
            await state.set_state(previous)
            await message.answer(f"Ок, вы вернулись к прошлому шагу \n {SessionState.texts[previous.state]}")
            return
        previous = step
        
        

# session list
@router.message(SESSION_MANAGMENT_KB_NAMES["session_list"] == F.text)
async def session_list(message: Message):
    sessions = await rq.orm_get_all_sessions()
    btns = {}

    if sessions:
        for session in sessions:
            btns[f"{session.id} - {session.session_type}"] = (
                f"session_settings_{session.id}"
            )

        await message.answer(
            "Список сесій 📕",
            reply_markup=get_callback_btns(btns=btns, sizes=(1,)),
        )
    else:
        await message.answer("Сесій немає", reply_markup=session_managment)


# session list
@router.callback_query(F.data == "session_list")
async def session_list(callback: CallbackQuery):
    sessions = await rq.orm_get_all_sessions()
    btns = {}

    for session in sessions:
        btns[f"{session.id} - {session.session_type}"] = (
            f"session_settings_{session.id}"
        )

    await callback.message.edit_text(
        "Список сесій 📕",
        reply_markup=get_callback_btns(btns=btns, sizes=(1,)),
    )


# session settings
@router.callback_query(F.data.startswith("session_settings_"))
async def session_settings(callback: CallbackQuery, state: FSMContext):
    session_id = int(callback.data.split("_")[-1])
    session = await rq.orm_get_session(session_id)

    if session:
        await callback.answer()

        text = f"Активна сесія: {'✅' if session.is_active else '❌'}\nID: <code>{session.id}</code>\nСесія: {session.session_type}\nКількість аккаунтів: {session.account_count}\n\nПромпт:\n{session.prompt}\n"
        btns = {}

        if session.is_active:
            btns["Зупинити сесію"] = f"stop_session_{session.id}"
        else:
            btns["Розпочати сесію"] = f"start_session_{session.id}"

        btns["Назад"] = "session_list"

        await callback.message.edit_text(
            text, reply_markup=get_callback_btns(btns=btns, sizes=(1,))
        )


# remove session
@router.message(SESSION_MANAGMENT_KB_NAMES["remove_session"] == F.text)
async def remove_session(message: Message, state: FSMContext):
    await message.answer("Введіть ID сесіі", reply_markup=back_session_managment)
    await state.set_state(SessionState.remove_session)


@router.message(SessionState.remove_session)
async def remove_session(message: Message, state: FSMContext):
    await state.update_data(session_id=message.text)

    data = await state.get_data()
    session_id = data.get("session_id")

    if session_id is None:
        await message.answer("Введіть ID сесіі", reply_markup=session_managment)
        return

    session = await rq.orm_get_session(int(session_id))

    if session is None:
        await message.answer("Сесія не знайдена", reply_markup=session_managment)
        return

    remove_result = await rq.orm_remove_session(int(session_id))

    if remove_result:
        await message.answer("Сесію успішно видалено", reply_markup=session_managment)
    else:
        await message.answer(
            "Помилка при видаленні сесіі", reply_markup=session_managment
        )

    await state.clear()

