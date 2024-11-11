import asyncio
import os
import traceback
import logging

import app.keyboards.admin_keyboard as kb

from datetime import datetime, timedelta

from aiogram.types import Message, FSInputFile
from pyrogram import Client
from pyrogram.errors import (
    FloodWait,
    ChannelPrivate,
    UsernameInvalid,
    InviteRequestSent,
    UsernameNotOccupied,
)
from dotenv import load_dotenv

from app.database.orm_query import (
    orm_channel_processed,
    orm_add_channel,
    orm_get_users,
    orm_set_account_active,
    orm_get_accounts,
    orm_update_flood_wait,
)
from app.utils.helpers import load_excel_data, random_sleep


logger = logging.getLogger(__name__)
load_dotenv()


class ChatJoiner:
    def __init__(self, message: Message):
        self.message: Message = message
        self.data, self.count = load_excel_data()
        self.users = None

    log_file_path = "D:\\projects\\seo-group-tg-bot\\channel_log.txt"

    async def start(self, client: Client):
        await client.start()

    async def stop(self, client: Client):
        await client.stop()

    async def send_message_to_all_admins(self, text: str):
        for user in self.users:
            if user.is_admin:
                await self.message.bot.send_message(user.tg_id, text)

    async def log_channel_status(self, chat_url, success=True, text=""):
        status = "Успішно додано" if success else "Неуспішно додано"

        with open("channel_log.txt", "a", encoding="utf-8") as file:
            file.write(f"{status}: {chat_url} - {text}\n")

    async def join_chats(self, country: str, city: str, is_general: bool):
        while True:
            try:
                accounts = await orm_get_accounts()
                number = 1

                for account in accounts:
                    # if account active - continue
                    if account.is_active:
                        continue

                    # check phone number
                    phone_number = account.phone_number
                    if not phone_number:
                        continue

                    # check if flood wait set
                    if account.flood_wait:
                        # check if flood wait has done
                        if account.flood_wait > datetime.now():
                            continue

                    client = Client(
                        f"sessions/{phone_number}"
                    )  # connect to user account
                    await orm_set_account_active(
                        phone_number, True
                    )  # set active status for the number

                    try:
                        # start tg session
                        await self.start(client)

                        self.users = await orm_get_users()

                        for i, item in enumerate(self.data[number:], number):
                            if self.count == 1:
                                await self.message.answer(
                                    "В базі має бути декілька груп", reply_markup=kb.admin_menu
                                )
                                return

                            if i >= self.count:
                                return

                            if i % 10 == 0:
                                await self.message.answer(
                                    f"Chat Joiner {phone_number} пройшовся вже по {i} групам"
                                )

                            chat = item[0].split("/")[-1]

                            channel_processed, channel_processed_phone_number = (
                                await orm_channel_processed(chat)
                            )
                            if channel_processed:
                                logger.info(f"Вже є в базі {item[0]}")
                                await self.log_channel_status(
                                    item[0],
                                    success=False,
                                    text=f"Вже є в базі / {channel_processed_phone_number} / {channel_processed.country} / {channel_processed.city} / {channel_processed.is_general}",
                                )
                                continue

                            try:
                                await client.join_chat(chat)
                                await orm_add_channel(
                                    chat, phone_number, True, country, city, is_general
                                )
                                await random_sleep()

                                logger.info(f"Успішне додавання {item[0]}")
                                await self.log_channel_status(
                                    item[0],
                                    success=True,
                                    text=f"{phone_number} / {country} / {city} / {is_general}",
                                )
                            except InviteRequestSent:
                                logger.warning(
                                    f"Запит на приєднання до {chat} вже надісланий. Чекаємо на схвалення."
                                )
                                await orm_add_channel(
                                    chat, phone_number, True, country, city, is_general
                                )
                                await self.log_channel_status(
                                    item[0],
                                    success=True,
                                    text=f"Успішне додавання, чекає на схвалення / {channel_processed_phone_number} / {channel_processed.country} / {channel_processed.city} / {channel_processed.is_general}",
                                )
                            except ChannelPrivate:
                                logger.warning(
                                    f"Не вдалося приєднатися до {chat}: канал приватний."
                                )
                                await orm_add_channel(
                                    chat, phone_number, False, country, city, is_general
                                )
                                await self.log_channel_status(
                                    item[0],
                                    success=False,
                                    text=f"{channel_processed_phone_number} / {channel_processed.country} / {channel_processed.city} / {channel_processed.is_general}",
                                )
                            except UsernameInvalid:
                                logger.warning(f"Неправильний або недійсний {item[0]}")
                                await orm_add_channel(
                                    chat, phone_number, False, country, city, is_general
                                )
                                await self.log_channel_status(
                                    item[0],
                                    success=False,
                                    text=f"{channel_processed_phone_number} / {channel_processed.country} / {channel_processed.city} / {channel_processed.is_general}",
                                )
                            except UsernameNotOccupied:
                                logger.warning(
                                    f"Канал з назвою {item[0]} не існує або він видалений."
                                )
                                await orm_add_channel(
                                    chat, phone_number, False, country, city, is_general
                                )
                                await self.log_channel_status(
                                    item[0],
                                    success=False,
                                    text=f"{channel_processed_phone_number} / {channel_processed.country} / {channel_processed.city} / {channel_processed.is_general}",
                                )
                            except FloodWait as e:
                                wait_until = datetime.now() + timedelta(seconds=e.value)
                                logger.warning(
                                    f"FloodWait: необхідно зачекати до {wait_until}"
                                )
                                await self.message.answer(
                                    f"{phone_number} получив flood_wait бан до {wait_until}"
                                )
                                await orm_update_flood_wait(phone_number, wait_until)
                                number = i
                                break
                            except Exception as e:
                                logger.warning(f"Error: {e}\n\n{chat}")
                                await self.message.bot.send_message(
                                    chat_id=os.getenv("DEV_CHAT_ID"),
                                    text=f"Error: {e}\n\n{chat}",
                                )
                                await orm_add_channel(
                                    chat, phone_number, False, country, city, is_general
                                )
                                await self.log_channel_status(
                                    item[0],
                                    success=False,
                                    text=f"{channel_processed_phone_number} / {channel_processed.country} / {channel_processed.city} / {channel_processed.is_general}",
                                )
                    finally:
                        await orm_set_account_active(phone_number, False)
                        await self.stop(client)
            except Exception as e:
                # show error
                error_message = traceback.format_exc()
                logger.error(f"CHAT JOINER / ERROR: {e}\n{error_message}")

                await self.send_message_to_all_admins(f"Error: {e}\n{error_message}")

                return
            finally:
                if not os.path.getsize(self.log_file_path) == 0:
                    await self.message.answer(
                        "Додавання чатів зупинено", reply_markup=kb.admin_menu
                    )
                    info_file = FSInputFile(self.log_file_path, filename="result.txt")
                    await self.message.bot.send_document(
                        chat_id=self.message.chat.id, document=info_file
                    )

                    with open(self.log_file_path, "w", encoding="utf-8") as file:
                        pass
                else:
                    await self.message.answer(
                        "Додавання чатів зупинено (не було додано жодної групи)",
                        reply_markup=kb.admin_menu,
                    )