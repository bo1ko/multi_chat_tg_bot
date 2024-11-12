import asyncio
import logging
import os
import traceback
from datetime import datetime, timedelta

from aiogram.types import Message
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.errors import (
    UserNotParticipant,
    ChannelPrivate,
    UsernameInvalid,
    UsernameNotOccupied,
    InviteRequestSent
)

from app.database.orm_query import (
    orm_get_account_by_id,
    orm_get_dialogs,
    orm_get_session,
    orm_update_account,
    orm_update_session,
)
from app.utils.helpers import generate_answer_for_user, is_proxy_working, random_number, write_unique_message, clear_unique_message

logger = logging.getLogger(__name__)
load_dotenv()


class ChatJoiner:
    def __init__(self, message: Message, admin_menu):
        self.message: Message = message
        self.admin_menu = admin_menu
        self.phone_number = None
        self.sent_answer = False

    async def start_chatting(self, session_id):
        try:
            session = await orm_get_session(session_id)

            if not session:
                await self.message.answer(
                    "Сесія не знайдена", reply_markup=self.admin_menu
                )
                return

            if not session.is_dialog_created:
                await self.message.answer(
                    "Сесія не має створених діалогів", reply_markup=self.admin_menu
                )
                return

            if session.is_active:
                await self.message.answer(
                    "Сесія вже активна", reply_markup=self.admin_menu
                )
                return

            update_session = await orm_update_session(session_id, is_active=True)

            if not update_session:
                await self.message.answer(
                    "Не вдалося активувати сесію!", reply_markup=self.admin_menu
                )
                return

            dialogs = await orm_get_dialogs(session_id)

            if not dialogs:
                await self.message.answer(
                    "Не має створених діалогів для цієї сесії",
                    reply_markup=self.admin_menu,
                )
                return

            usernames = []

            for count, dialog in enumerate(dialogs):
                print(dialog.message_id, dialog.message)
                try:
                    first, last = session.answer_time.split("-")
                    sleep_time = random_number(int(first), int(last))
                    account = await orm_get_account_by_id(dialog.account_id)

                    while True:
                        if not account.is_active:
                            break

                        account = await orm_get_account_by_id(dialog.account_id)
                        await asyncio.sleep(5)

                    # Check phone number
                    self.phone_number = account.number
                    if not self.phone_number:
                        continue

                    
                    try:
                        scheme = account.proxy.split("://")[0]
                        parsed_proxy = account.proxy.split("://")[1].split(":")

                        proxy = {
                            "hostname": parsed_proxy[1].split("@")[1],
                            "port": int(parsed_proxy[2]),
                            "username": parsed_proxy[0],
                            "password": parsed_proxy[1].split("@")[0],
                            "scheme": scheme
                        }
                    except Exception as e:
                        print(e)
                        await self.message.answer(f'Невалідний проксі {account.proxy} для номера {account.number}', reply_markup=self.admin_menu)
                        return
                    
                    result = await is_proxy_working(account.proxy)
                    if not result:
                        await self.message.answer(
                            f"Помилка при підключенні до Telegram (Проксі не дає відповідь)", reply_markup=self.account_managment
                        )
                        return
                    
                    await orm_update_account(self.phone_number, is_active=True)

                    async with Client(f"sessions/{self.phone_number}", proxy=proxy) as client:
                        chat_url = session.chat_url.split("/")[-1]

                        try:
                            try:
                                chat = await client.get_chat(chat_url)
                                await client.get_chat_member(
                                    chat.id, client.me.id
                                )
                            except UserNotParticipant:
                                await client.join_chat(chat_url)


                            async for group in client.get_dialogs():
                                # Check if the chat has unread messages
                                if group.chat.username == chat_url:
                                    if client.me.username not in usernames:
                                        usernames.append(client.me.username)
                                        
                                        await client.read_chat_history(group.chat.id)
                                        continue
                                    
                                    if group.unread_messages_count > 0:
                                        print(
                                            f"Unread messages in chat with ID {group.chat.id}: {group.unread_messages_count}"
                                        )

                                        # Fetch the chat history for unread messages
                                        await client.read_chat_history(group.chat.id)
                                        async for (
                                                group_message
                                        ) in client.get_chat_history(
                                            group.chat.id,
                                            limit=group.unread_messages_count,
                                        ):
                                            if group_message.from_user.username not in usernames:
                                                result = write_unique_message(self.phone_number, group_message.text)

                                                if result:
                                                    print(
                                                        f"From {group_message.from_user.first_name}: {group_message.text}"
                                                    )
                                                    answer = await generate_answer_for_user(session_id,
                                                                                            group_message.text,
                                                                                            self.message,
                                                                                            self.admin_menu)

                                                    if answer:
                                                        await client.send_message(
                                                            group.chat.id,
                                                            text=answer,
                                                            reply_to_message_id=group_message.id,
                                                        )
                                                        self.sent_answer = True

                            if self.sent_answer:
                                logging.info(f"Answer got. Sleep time: {sleep_time}")
                                await asyncio.sleep(sleep_time / 2)
                                self.sent_answer = False
                            # CONTINUE DIALOG BETWEEN BOTS
                            await client.send_message(chat_url, str(dialog.message))

                            logger.info(
                                f"Sleep time: {sleep_time}"
                            )

                        except (
                                ChannelPrivate,
                                UsernameInvalid,
                                UsernameNotOccupied,
                        ) as e:
                            # If the chat does not exist or access error
                            logging.error(f"Error: {e}\n\n{chat_url}")
                            continue
                        except InviteRequestSent:
                            # If a request for admission is sent, but not admission
                            logging.error(f"Error: {e}\n\n{chat_url}")
                        except Exception as e:
                            logger.warning(f"Error: {e}\n\n{chat_url}")
                            await self.message.bot.send_message(
                                chat_id=os.getenv("DEV_CHAT_ID"),
                                text=f"Error: {e}\n\n{chat_url}",
                            )
                finally:
                    await orm_update_account(self.phone_number, is_active=False)
                    logging.info(f"Sleep time: {sleep_time}")
                    await asyncio.sleep(sleep_time)


            await self.message.answer(
                "Ділоги закінчились. Процес зупинено.", reply_markup=self.admin_menu
            )
        except Exception as e:
            # show error
            error_message = traceback.format_exc()
            logger.error(f"CHAT JOINER / ERROR: {e}\n{error_message}")

            await self.message.answer(
                f"Додавання чатів зупинено з помилкою:\n\n{error_message}",
                reply_markup=self.admin_menu,
            )
            return
        finally:
            self.phone_number = None
            clear_unique_message(self.phone_number)
            await orm_update_session(session_id, is_active=False)
