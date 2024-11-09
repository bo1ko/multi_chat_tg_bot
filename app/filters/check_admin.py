from aiogram.filters import Filter
from aiogram.types import Message

from app.database.orm_query import orm_is_admin


class IsAdmin(Filter):
    def __init__(self) -> None:
        pass

    async def __call__(self, message: Message):
        return await orm_is_admin(message.from_user.id)
