from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from dotenv import load_dotenv

from app.database.orm_query import orm_get_user, orm_add_user
from app.filters.check_admin import IsAdmin
from app.handlers.admin_handler import admin_menu

load_dotenv()

router = Router()


#  /start
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()

    user = await orm_get_user(value=message.from_user.id, get_by="id")

    if not user:
        await orm_add_user(message.from_user.id, message.from_user.username)
    elif await IsAdmin().__call__(message):
        await message.answer("Вітаю! 😊", reply_markup=admin_menu)
