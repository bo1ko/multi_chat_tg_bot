import asyncio
import os

from aiogram import Router, types, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, or_f, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from dotenv import load_dotenv
import validators

from app.bots.chat_bot import ChatJoiner
import app.database.orm_query as rq

from app.bots.auth import TelegramLogin
from app.keyboards.reply import get_keyboard
from app.keyboards.inline import get_callback_btns

from app.filters.check_admin import IsAdmin
from app.bots.get_account_app_data import AuthTgAPI
from app.utils.helpers import clear_folder, generate_dialogs, roles_distribution
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
    "telegram_auth_proccess": "Авторизація Telegram 🚀",
    "back_account_managment": '⬅️ Назад до меню "Аккаунти"',
}
account_managment = get_keyboard(
    ACCOUNT_MANAGMENT_KB_NAMES["account_list"],
    ACCOUNT_MANAGMENT_KB_NAMES["add_accounts"],
    ACCOUNT_MANAGMENT_KB_NAMES["remove_account"],
    ACCOUNT_MANAGMENT_KB_NAMES["telegram_auth_proccess"],
    BACK_TO_MENU["back_to_menu"],
    sizes=(1, 2, 1),
)
back_account_managment = get_keyboard(
    ACCOUNT_MANAGMENT_KB_NAMES["back_account_managment"]
)


class AccountState(StatesGroup):
    add_accounts = State()
    remove_accounts = State()
    two_code = State()
    proxy = State()


@router.message(
    or_f(
        (ADMIN_MENU_KB_NAMES["accounts"] == F.text),
        (ACCOUNT_MANAGMENT_KB_NAMES["back_account_managment"] == F.text),
    )
)
async def account_panel(message: Message, state: FSMContext):
    global auth_task

    if auth_task and not auth_task.done():
        auth_task.cancel()
        try:
            await auth_task
        except asyncio.CancelledError:
            await message.answer("Телеграм авторизація була скасована.")

    await message.answer('Розділ "Аккаунти 🔑"', reply_markup=account_managment)
    await state.clear()


# account list
@router.message(ACCOUNT_MANAGMENT_KB_NAMES["account_list"] == F.text)
async def account_list(message: Message, state: FSMContext):
    accounts = await rq.orm_get_all_accounts()
    account_messages = []

    msg = await message.answer("Список аккаунтів 👇", reply_markup=account_managment)
    account_messages.append(msg.message_id)

    if not accounts:
        await message.answer("Список аккаунтів порожній", reply_markup=account_managment)
        return

    for account in accounts:
        text = f"Номер: <code>{account.number}</code>\n"
        text += f"2-х код: <code>{account.two_auth_code}</code>\n"
        text += f"Проксі: <code>{account.proxy}</code>\n"
        text += f"Додаток створений: {'✅' if account.is_app_created else '❌'}\n"
        if account.is_app_created:
            text += f"API ID: <code>{account.api_id}</code>\n"
            text += f"API HASH: <code>{account.api_hash}</code>\n"
            text += f"Сесія створена: {'✅' if account.is_session_created else '❌'}\n"
            if account.is_session_created:
                text += f"ID сесіі: {account.session_id}\n"

        btns = {'Редагувати': f"edit_account_{account.id}"}
        msg = await message.answer(text, reply_markup=get_callback_btns(btns=btns, sizes=(1,)))
        account_messages.append(msg.message_id)
        
    await state.update_data(account_messages=account_messages)

@router.callback_query(F.data.startswith("edit_account_"))
async def edit_account(callback: CallbackQuery, state: FSMContext):
    account_id = int(callback.data.split("_")[-1])
    account = await rq.orm_get_account_by_id(int(account_id))

    # Retrieve the list of message IDs to delete
    data = await state.get_data()
    account_messages = data.get("account_messages", [])

    # Delete all the account list messages
    for msg_id in account_messages:
        try:
            await callback.message.chat.delete_message(msg_id)
        except Exception as e:
            # Handle any exceptions, for example if the message is already deleted
            print(f"Failed to delete message {msg_id}: {e}")
    
    if account:
        btns = {
            'Змінити код': f"change_two_auth_code_{account.id}",
            'Змінити проксі': f"change_proxy_{account.id}",
            'Назад': f"back_to_account_list",
        }
        await callback.message.answer(f"Аккаунт:\nНомер: <code>{account.number}</code>\nКод: <code>{account.two_auth_code}</code>\nПроксі: <code>{account.proxy}</code>", reply_markup=get_callback_btns(btns=btns, sizes=(1,)))

@router.callback_query(F.data.startswith("change_two_auth_code_"))
async def change_two_auth_code(callback: CallbackQuery, state: FSMContext):
    account_id = int(callback.data.split("_")[-1])
    
    await callback.message.delete()
    await callback.message.answer('Введіть 2-х код:', reply_markup=back_account_managment)
    await state.set_data({"account_id": account_id})
    await state.set_state(AccountState.two_code)

@router.message(AccountState.two_code)
async def change_two_auth_code_second(message: Message, state: FSMContext):
    two_code = message.text
    account_id = await state.get_value("account_id")

    result = await rq.orm_update_account_by_id(account_id, two_auth_code=two_code)  
    
    if result:
        await message.answer("2-х код успішно змінено")
    else:
        await message.answer("2-х код не змінено")
    
    await state.clear()
    await account_list(message, state)

@router.callback_query(F.data.startswith("change_proxy_"))
async def change_proxy(callback: CallbackQuery, state: FSMContext):
    account_id = int(callback.data.split("_")[-1])
    
    await callback.message.delete()
    await callback.message.answer('Введіть проксі:', reply_markup=back_account_managment)
    await state.set_data({"account_id": account_id})
    await state.set_state(AccountState.proxy)

@router.message(AccountState.proxy)
async def change_proxy_second(message: Message, state: FSMContext):
    proxy = message.text
    account_id = await state.get_value("account_id")

    result = await rq.orm_update_account_by_id(account_id, proxy=proxy)  
    
    if result:
        await message.answer("Проксі успішно змінено")
    else:
        await message.answer("Проксі не змінено")
    
    await state.clear()
    await account_list(message, state)

@router.callback_query(F.data == "back_to_account_list")
async def back_to_account_list(callback: CallbackQuery, state: FSMContext):
    accounts = await rq.orm_get_all_accounts()
    account_messages = []

    await callback.answer()
    
    if not accounts:
        await callback.message.answer("Список аккаунтів порожній", reply_markup=account_managment)
        return

    msg = await callback.message.answer("Список аккаунтів 👇", reply_markup=account_managment)
    account_messages.append(msg.message_id)

    for account in accounts:
        text = f"Номер: <code>{account.number}</code>\n"
        text += f"2-х код: <code>{account.two_auth_code}</code>\n"
        text += f"Проксі: <code>{account.proxy}</code>\n"
        text += f"Додаток створений: {'✅' if account.is_app_created else '❌'}\n"
        if account.is_app_created:
            text += f"API ID: <code>{account.api_id}</code>\n"
            text += f"API HASH: <code>{account.api_hash}</code>\n"
            text += f"Сесія створена: {'✅' if account.is_session_created else '❌'}\n"
            if account.is_session_created:
                text += f"ID сесії: {account.session_id}\n"

        btns = {'Редагувати': f"edit_account_{account.id}"}
        msg = await callback.message.answer(text, reply_markup=get_callback_btns(btns=btns, sizes=(1,)))
        account_messages.append(msg.message_id)
    
    await state.update_data(account_messages=account_messages)

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
    await message.answer("Введіть номера:", reply_markup=back_account_managment)
    await state.set_state(AccountState.remove_accounts)


@router.message(AccountState.remove_accounts)
async def remove_account_second(message: Message, state: FSMContext):
    numbers = message.text

    if numbers is None:
        await message.reply(
            "Будь ласка, надішліть правильний номер.",
            reply_markup=account_managment,
        )
        await state.clear()
        return

    accounts = await rq.orm_get_all_accounts()
    for account in accounts:
        if account.number in numbers:
            await rq.orm_remove_account(account.number)
            await message.reply(
                f"Аккаунт <code>{account.number}</code> успішно видалений",
                reply_markup=account_managment,
            )

    await state.clear()


# ---------- TG AUTH ----------
class Auth(StatesGroup):
    code = State()
    two_auth = State()


login_manager = None
auth_task = None


# telegram auth
@router.message(ACCOUNT_MANAGMENT_KB_NAMES["telegram_auth_proccess"] == F.text)
async def api_auth(message: Message, state: FSMContext):
    await state.clear()
    await message.answer('Виберіть номер для авторизації', reply_markup=back_account_managment)

    accounts = await rq.orm_get_authorized_accounts_without_session()
    btns = {}
    
    for account in accounts:
        btns[f'{account.number}'] = f'start_auth_tg_{account.id}'
        
    await message.answer(f'Номера 📱', reply_markup=get_callback_btns(btns=btns, sizes=(1,)))
    

@router.callback_query(F.data.startswith("start_auth_tg_"))
async def start_auth_tg(callback: CallbackQuery, state: FSMContext):
    global auth_task, login_manager
    
    account_id = int(callback.data.split("_")[-1])

    if auth_task and not auth_task.done():
        auth_task.cancel()
        login_manager = None

    await callback.message.edit_text("Розпочинаю Telegram авторизацію...")

    account = await rq.orm_get_account_by_id(account_id)

    # await login_manager.start_login(callback.message, state)
    login_manager = TelegramLogin(account_managment)
    auth_task = asyncio.create_task(login_manager.start_login(callback.message, account))
    await state.set_state(Auth.code)


@router.message(Auth.code)
async def code_handler(message: types.Message, state: FSMContext):
    if message.text and message.text.isdigit():
        global auth_task, login_manager

        code_text = message.text
        auth_task = await login_manager.finish_login(message, code_text)

        await state.clear()
    else:
        await message.answer("Будь ласка, введи коректний код підтвердження.")


# ---------- SESSION ----------
# session panel
SESSION_MANAGMENT_KB_NAMES = {
    "add_session": "Добавити сесію 💻",
    "remove_session": "Видалити сесію 🗑️",
    "session_list": "Список сесій 📕",
    "additional instructions": "Додаткові вказівки 📝",
    "step_back": "Крок назад",
    "back_session_managment": "⬅️ Назад до панелі сесій",
}
session_managment = get_keyboard(
    SESSION_MANAGMENT_KB_NAMES["session_list"],
    SESSION_MANAGMENT_KB_NAMES["add_session"],
    SESSION_MANAGMENT_KB_NAMES["remove_session"],
    SESSION_MANAGMENT_KB_NAMES["additional instructions"],
    BACK_TO_MENU["back_to_menu"],
    sizes=(1, 2, 1, 1),
)
back_session_managment = get_keyboard(
    SESSION_MANAGMENT_KB_NAMES["back_session_managment"],
    sizes=(1, 1),
)

back_from_add_session = get_keyboard(
    SESSION_MANAGMENT_KB_NAMES["step_back"],
    SESSION_MANAGMENT_KB_NAMES["back_session_managment"],
    sizes=(1, 1),
)

chat_bot = None
chat_bot_task = None


class SessionState(StatesGroup):
    session_type = State()
    prompt = State()
    account_count = State()
    chat_url = State()
    answer_time = State()
    set_instructions = State()
    edit_instructions = State()

    remove_session = State()

    texts = {
        "SessionState:session_type": "Введіть тип сесії заново:",
        "SessionState:prompt": "Введіть промпт заново:",
        "SessionState:chat_url": "Введіть посилання на чат заново:",
        "SessionState:answer_time": "Введіть проміжок часу між відповідями користувачів заново:",
    }


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
@router.message(StateFilter(None), SESSION_MANAGMENT_KB_NAMES["add_session"] == F.text)
async def add_session_first(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Введіть назву сесії 👇", reply_markup=back_from_add_session)
    await state.set_state(SessionState.session_type)


@router.message(StateFilter("*"), F.text.casefold() == "крок назад")
async def back_step_handler(message: types.Message, state: FSMContext):

    current_state = await state.get_state()
    print("!" * 10, current_state)
    if current_state == SessionState.session_type:
        await message.answer(
            "Попередній крок відсутній, або введіть назву сесії, або вийдіть в меню"
        )
        return

    previous = None
    for step in SessionState.__all_states__:
        if step.state == current_state:
            await state.set_state(previous)
            await message.answer(
                f"Ок, ви повернулися до попереднього кроку \n{SessionState.texts[previous.state]}"
            )
            return
        previous = step


@router.message(SessionState.session_type, F.text)
async def add_session_second(message: Message, state: FSMContext, back=False):
    if not back:
        await state.update_data(session_type=message.text)
    await message.answer("Введіть промпт 👇", reply_markup=back_from_add_session)
    await state.set_state(SessionState.prompt)


@router.message(SessionState.session_type)
async def add_session_fifth_wrong(message: types.Message):
    await message.answer("Ви ввели недопустимі дані, введіть назву знову")


@router.message(SessionState.prompt, F.text)
async def add_session_third(message: Message, state: FSMContext):
    prompt = message.text

    result = await generate_dialogs(prompt, message, back_from_add_session)

    if not result:
        await message.answer(
            "Помилка при отриманні JSON з відповіді GPT. Спробуйте ще раз згенерувати діалог.\n\nВведіть промпт 👇",
            reply_markup=back_from_add_session,
        )
        return

    await state.update_data(data_json=result)


@router.message(SessionState.prompt)
async def add_session_fifth_wrong(message: types.Message):
    await message.answer("Ви ввели недопустимі дані, введіть провіжок часу знову")


@router.callback_query(F.data == "use_dialog")
async def use_dialog(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text("Діалог підтверджено")

    await callback.message.answer(
        "Введіть посилання на чат 👇", reply_markup=back_from_add_session
    )

    await state.set_state(SessionState.chat_url)


@router.callback_query(F.data == "dont_use_dialog")
async def dont_use_dialog(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text("Діалог скасовано")
    await add_session_second(callback.message, state, back=True)


@router.message(SessionState.chat_url, F.text)
async def add_session_fourth(message: Message, state: FSMContext):
    url = message.text

    if validators.url(url):
        await message.answer("Юрл підійшов", reply_markup=back_from_add_session)
        await state.update_data(chat_url=message.text)

        await message.answer(
            "Введіть проміжок часу між відповідями користувачів (секунди)\nПриклад: 60-120, 35-60, 20-30",
            reply_markup=back_from_add_session,
        )
        await state.set_state(SessionState.answer_time)
    else:
        await message.answer(
            "Юрл не валідний, введіть юрл чату знову",
            reply_markup=back_from_add_session,
        )
        return


@router.message(SessionState.chat_url)
async def add_session_fifth_wrong(message: types.Message):
    await message.answer("Ви ввели недопустимі дані, введіть юрл чату знову")


@router.message(SessionState.answer_time, F.text)
async def add_session_fifth(message: Message, state: FSMContext):
    answer_time = message.text.split("-")

    if len(answer_time) != 2:
        await message.answer(
            "Введіть правильний проміжок часу між відповідями користувачів",
            reply_markup=back_from_add_session,
        )
        return

    print("!" * 10, int(answer_time[0]) <= int(answer_time[1]))
    if int(answer_time[0]) >= int(answer_time[1]):
        await message.answer(
            "Введіть правильний проміжок часу між відповідями користувачів",
            reply_markup=back_from_add_session,
        )
        return

    await state.update_data(answer_time=message.text)

    data = await state.get_data()

    session_type = data.get("session_type")
    data_json = data.get("data_json")
    chat_url = data.get("chat_url")

    add_session = await rq.orm_add_session(
        session_type, data_json, chat_url, message.text
    )

    if add_session:
        await message.answer("Сесія збережена!")
        await message.answer(
            f"Назва: {session_type}\nЮрл чату: {chat_url}\nСередній час відповіді: {message.text}",
            reply_markup=session_managment,
        )
        await message.answer(
            "Починаю розприділяти ролі по аккаунтам", reply_markup=session_managment
        )

        accounts = await rq.orm_get_free_accounts()
        session = await rq.orm_get_session(add_session.id)
        result_status, result_text = await roles_distribution(
            session.id, accounts, session.data
        )

        if result_status:
            await message.answer(
                f"Результат: {result_text}", reply_markup=session_managment
            )
            await rq.orm_update_session(add_session.id, is_dialog_created=True)
        else:
            await message.answer(result_text, reply_markup=session_managment)
    else:
        await message.answer("Щось пішло не так.. Спробуйте знову!")

    await state.clear()


@router.message(SessionState.answer_time)
async def add_session_fifth_wrong(message: types.Message):
    await message.answer("Ви ввели недопустимі дані, введіть провіжок часу знову")


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
async def session_settings(callback: CallbackQuery):
    session_id = int(callback.data.split("_")[-1])
    session = await rq.orm_get_session(session_id)

    if session:
        await callback.answer()

        text = f"Активна сесія: {'✅' if session.is_active else '❌'}\nID: <code>{session.id}</code>\nСесія: {session.session_type}\nЧат: {session.chat_url}\nЧас відповіді: {session.answer_time}\n"

        if session.instructions:
            text += f"Інструкція: {session.instructions}"
        btns = {}

        if not session.is_dialog_created:
            btns["Створити діалог"] = f"start_dialog_{session.id}"
        else:
            if session.is_active:
                btns["Зупинити сесію"] = f"stop_session_{session.id}"
            else:
                btns["Розпочати сесію"] = f"start_session_{session.id}"

        btns["Назад"] = "session_list"

        await callback.message.edit_text(
            text, reply_markup=get_callback_btns(btns=btns, sizes=(1,))
        )


@router.callback_query(F.data.startswith("start_dialog_"))
async def start_dialog(callback: CallbackQuery, state: FSMContext):
    session_id = int(callback.data.split("_")[-1])

    await callback.answer()
    message_info = await callback.message.answer(
        "Починаю розприділяти ролі по аккаунтам"
    )

    accounts = await rq.orm_get_free_accounts()
    session = await rq.orm_get_session(session_id)
    result_status, result_text = await roles_distribution(
        session.id, accounts, session.data
    )

    if result_status:
        await session_settings(callback)

        message_result = await callback.message.answer(f"Результат: {result_text}")
        await rq.orm_update_session(session_id, is_dialog_created=True)

        await asyncio.sleep(2)
        await message_info.delete()
        await message_result.delete()
    else:
        await callback.message.answer(result_text, reply_markup=session_managment)


@router.callback_query(F.data.startswith("start_session_"))
async def start_chatting_session(callback: CallbackQuery, state: FSMContext):
    global chat_bot, chat_bot_task

    if chat_bot_task and not chat_bot_task.done():
        chat_bot_task.cancel()

    session_id = int(callback.data.split("_")[-1])
    chat_bot = ChatJoiner(callback.message, admin_menu)
    chat_bot_task = asyncio.create_task(chat_bot.start_chatting(session_id))

    if chat_bot_task.done():
        await callback.answer("Сесія не запустилась...", reply_markup=session_managment)
    else:
        await callback.answer("Сесія запущена", reply_markup=session_managment)
        await session_settings(callback)

    await state.clear()


@router.callback_query(F.data.startswith("stop_session_"))
async def stop_chatting_session(callback: CallbackQuery, state: FSMContext):
    global chat_bot, chat_bot_task

    if chat_bot_task and not chat_bot_task.done():
        chat_bot_task.cancel()
        await callback.answer("Сесію зупинено", reply_markup=session_managment)
        await session_settings(callback)
    else:
        await callback.answer("Сесія не запущена", reply_markup=session_managment)

    await state.clear()


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


@router.message(SESSION_MANAGMENT_KB_NAMES["additional instructions"] == F.text)
async def additional_instructions(message: Message, state: FSMContext):
    await message.answer("Виберіть сесію", reply_markup=back_session_managment)
    sessions = await rq.orm_get_all_sessions()
    if sessions:
        for session in sessions:
            btns = {}
            text = f"👉 {session.session_type} (ID: {session.id})"
            if session.instructions:
                text += f"\n\n📃 {session.instructions}"
                btns = {"Змінити": f"session_edit_{session.id}"}
                btns["Видалити"] = f"remove_session_{session.id}"
            else:
                btns = {"Встановити": f"session_edit_{session.id}"}

            await message.answer(
                text, reply_markup=get_callback_btns(btns=btns, sizes=(1,))
            )


@router.callback_query(F.data.startswith("session_edit_"))
async def set_instructions(callback: CallbackQuery, state: FSMContext):
    session_id = int(callback.data.split("_")[-1])
    await state.clear()
    await callback.answer()
    await callback.message.answer("Введіть інструкцію")
    await state.set_state(SessionState.edit_instructions)
    await state.update_data(session_id=session_id)


@router.message(SessionState.edit_instructions)
async def set_instructions(message: Message, state: FSMContext):
    data = await state.get_data()
    session_id = data.get("session_id")
    await rq.orm_update_session(session_id, instructions=message.text)
    await message.answer("Інструкцію успішно змінено", reply_markup=session_managment)
    await state.clear()


@router.callback_query(F.data.startswith("remove_session_"))
async def remove_session(callback: CallbackQuery, state: FSMContext):
    session_id = int(callback.data.split("_")[-1])
    await callback.message.edit_text("Видалюємо інструкцію...")
    await rq.orm_update_session(session_id, instructions=None)
    await callback.message.answer(
        "Інструкцію успішно видалено", reply_markup=session_managment
    )
    await state.clear()


@router.message(Command("test"))
async def cmd_test(message: Message):
    chat_bot = ChatJoiner(message, admin_menu)
    await chat_bot.start_chatting(4)