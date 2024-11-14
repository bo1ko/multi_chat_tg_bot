import asyncio
import logging
import os
import traceback

from aiogram.types import Message
from dotenv import load_dotenv
from pyrogram import Client
from pyrogram.errors import (
    UserNotParticipant,
    ChannelPrivate,
    UsernameInvalid,
    UsernameNotOccupied,
    InviteRequestSent,
    UserDeactivatedBan
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
                        # Parse the proxy from account data
                        scheme = account.proxy.split("://")[0]
                        parsed_proxy = account.proxy.split("://")[1].split(":")
                        proxy = {
                            "hostname": parsed_proxy[1].split("@")[1],
                            "port": int(parsed_proxy[2]),
                            "username": parsed_proxy[0],
                            "password": parsed_proxy[1].split("@")[0],
                            "scheme": scheme,
                        }
                    except Exception as e:
                        await self.message.answer(
                            f"Невалідний проксі {account.proxy} для номера {account.number}",
                            reply_markup=self.account_managment,
                        )
                        return

                    
                    await orm_update_account(self.phone_number, is_active=True)

                    try:
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
                                    if group.chat.username == chat_url:
                                        if client.me.username not in usernames:
                                            usernames.append(client.me.username)
                                            await client.read_chat_history(group.chat.id)
                                            continue
                                        
                                        if group.unread_messages_count > 0:
                                            print(f"Unread messages in chat with ID {group.chat.id}: {group.unread_messages_count}")
                                            await client.read_chat_history(group.chat.id)
                                            async for group_message in client.get_chat_history(group.chat.id, limit=group.unread_messages_count):
                                                if group_message.from_user.username not in usernames:
                                                    result = write_unique_message(self.phone_number, group_message.text)

                                                    if result:
                                                        print(f"From {group_message.from_user.first_name}: {group_message.text}")
                                                        answer = await generate_answer_for_user(session_id, group_message.text, self.message, self.admin_menu)

                                                        if answer:
                                                            await client.send_message(group.chat.id, text=answer, reply_to_message_id=group_message.id)
                                                            self.sent_answer = True

                                if self.sent_answer:
                                    logging.info(f"Answer got. Sleep time: {sleep_time}")
                                    await asyncio.sleep(sleep_time / 2)
                                    self.sent_answer = False

                                await client.send_message(chat_url, str(dialog.message))

                                logger.info(f"Sleep time: {sleep_time}")

                            except (ChannelPrivate, UsernameInvalid, UsernameNotOccupied, InviteRequestSent) as e:
                                logging.error(f"Error: {e}\n\n{chat_url}")
                                continue
                            except UserDeactivatedBan as e:
                                # Handle user deactivation or ban
                                logging.error(f"User deactivated or banned: {e}\n\n{chat_url}")
                                await self.message.answer(f"Користувач деактивований або забанений: {chat_url}", reply_markup=self.admin_menu)
                                return
                            except Exception as e:
                                logger.warning(f"Error: {e}\n\n{chat_url}")
                                await self.message.bot.send_message(
                                    chat_id=os.getenv("DEV_CHAT_ID"),
                                    text=f"Error: {e}\n\n{chat_url}",
                                )
                    except UserDeactivatedBan as e:
                        logging.error(f"User deactivated or banned during client initialization: {e}")
                        await self.message.answer(f"Користувач деактивований або забанений: {self.phone_number}", reply_markup=self.admin_menu)
                        return
                    except Exception as e:
                        logger.warning(f"Error initializing client: {e}")
                        await self.message.bot.send_message(
                            chat_id=os.getenv("DEV_CHAT_ID"),
                            text=f"Error initializing client: {e}",
                        )
                        return
                finally:
                    await orm_update_account(self.phone_number, is_active=False)
                    logging.info(f"Sleep time: {sleep_time}")
                    await asyncio.sleep(sleep_time)

            await self.message.answer(
                "Ділоги закінчились. Процес зупинено.", reply_markup=self.admin_menu
            )

        except Exception as e:
            # Handle general errors
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
