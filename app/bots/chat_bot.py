import ast
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
    UserDeactivatedBan,
    FloodWait
)

from app.database.orm_query import (
    orm_get_account_by_id,
    orm_get_dialogs,
    orm_get_session,
    orm_update_account,
    orm_update_session,
)
from app.utils.helpers import (
    generate_answer_for_user,
    is_proxy_working,
    random_number,
    write_unique_message,
    clear_unique_message,
    continue_dialog,
)

logger = logging.getLogger(__name__)
load_dotenv()


class ChatJoiner:
    def __init__(self, message: Message, admin_menu):
        self.message: Message = message
        self.admin_menu = admin_menu
        self.phone_number = None
        self.sent_answer = False
        self.dialog_id = None

    async def start_chatting(self, session_id):
        
        try:
            while True:
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

                data_list = ast.literal_eval(session.data)
                user_ids = {message["user_id"] for message in data_list}
                print(f'Кількість юзерів: {user_ids}')
                
                for count, dialog in enumerate(dialogs):
                    if self.dialog_id:
                        if dialog.id < self.dialog_id:
                            continue
                    
                    self.dialog_id = dialog.id
                    
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

                        proxy_str = account.proxy
                        if account.proxy:
                            if "http" not in account.proxy:
                                proxy_str = "http://" + proxy_str

                            try:
                                # Parse the proxy from account data
                                scheme = proxy_str.split("://")[0]
                                parsed_proxy = proxy_str.split("://")[1].split(":")
                                proxy = {
                                    "hostname": parsed_proxy[1].split("@")[1],
                                    "port": int(parsed_proxy[2]),
                                    "username": parsed_proxy[0],
                                    "password": parsed_proxy[1].split("@")[0],
                                    "scheme": scheme,
                                }
                            except Exception as e:
                                await self.message.answer(
                                    f"Невалідний проксі {account.proxy} для номера {account.number}")
                                return
                        else:
                            proxy = account.proxy

                        result = await is_proxy_working(proxy_str)
                        if not result:
                            await self.message.answer(
                                f"Помилка при підключенні до Telegram (Проксі не дає відповідь)")

                        await orm_update_account(self.phone_number, is_active=True)

                        try:
                            async with Client(
                                f"sessions/{self.phone_number}", proxy=proxy
                            ) as client:
                                chat_url = session.chat_url.split("/")[-1]

                                try:
                                    try:
                                        try:
                                            chat = await client.get_chat(session.chat_url)
                                        except:
                                            chat = await client.get_chat(chat_url)
                                        
                                        await client.get_chat_member(chat.id, client.me.id)
                                    except (AttributeError, UserNotParticipant) as e:
                                        await client.join_chat(session.chat_url)

                                    async for group in client.get_dialogs():
                                        if group.chat.id == chat.id:
                                            if client.me.username not in usernames:
                                                usernames.append(client.me.username)
                                                await client.read_chat_history(
                                                    group.chat.id
                                                )
                                                continue

                                            if group.unread_messages_count > 0:
                                                print(
                                                    f"Unread messages in chat with ID {group.chat.id}: {group.unread_messages_count}"
                                                )
                                                await client.read_chat_history(
                                                    group.chat.id
                                                )
                                                async for (
                                                    group_message
                                                ) in client.get_chat_history(
                                                    group.chat.id,
                                                    limit=group.unread_messages_count,
                                                ):
                                                    if (
                                                        group_message.from_user.username
                                                        not in usernames
                                                    ):
                                                        result = write_unique_message(
                                                            self.phone_number,
                                                            group_message.text,
                                                        )

                                                        if result:
                                                            print(
                                                                f"From {group_message.from_user.first_name}: {group_message.text}"
                                                            )
                                                            answer = await generate_answer_for_user(
                                                                session_id,
                                                                group_message.text,
                                                                self.message,
                                                                self.admin_menu,
                                                            )

                                                            if answer:
                                                                await client.send_message(
                                                                    group.chat.id,
                                                                    text=answer,
                                                                    reply_to_message_id=group_message.id,
                                                                )
                                                                self.sent_answer = True
                                
                                    if self.sent_answer:
                                        logging.info(
                                            f"Answer got. Sleep time: {sleep_time}"
                                        )
                                        await asyncio.sleep(sleep_time / 2)
                                        self.sent_answer = False

                                    await client.send_message(chat.id, str(dialog.message))

                                    logger.info(f"Sleep time: {sleep_time}")
                                except FloodWait as e:
                                    # Handle the flood wait by stopping the process or informing the user
                                    wait_time = e.x  # This is the required wait time in seconds
                                    logging.warning(f"Telegram flood wait. Waiting for {wait_time} seconds.")
                                    await self.message.answer(
                                        f"Аккаунт {account.number} зупинено на {wait_time} (flod wait). Сесія очікує розбану",
                                        reply_markup=self.admin_menu,
                                    )
                                    asyncio.sleep(int(wait_time))
                                
                                except (
                                    ChannelPrivate,
                                    UsernameInvalid,
                                    UsernameNotOccupied,
                                ) as e:
                                    logging.error(f"Error: {e}\n\n{chat_url}")
                                    logging.error(f"Traceback: {traceback.format_exc()}")

                                    if isinstance(e, ChannelPrivate):
                                        # Якщо канал або група приватні, робимо запит для доступу
                                        logging.info(
                                            f"Запит доступу до приватного каналу: {chat_url}"
                                        )
                                        # Код для запиту доступу або перевірки статусу, наприклад, відправка запиту на запрошення
                                        await self.send_invite_request(session.chat_url)

                                    elif isinstance(e, UsernameInvalid):
                                        logging.error(
                                            f"Невірне ім'я користувача: {chat_url}"
                                        )

                                    elif isinstance(e, UsernameNotOccupied):
                                        logging.error(
                                            f"Канал з таким іменем не існує: {chat_url}"
                                        )

                                    continue

                                except InviteRequestSent as e:
                                    logging.warning(
                                        f"Запит на запрошення вже надіслано для: {chat_url}"
                                    )
                                    # Тут можливо варто реалізувати логіку для повторної спроби або інших дій
                                    continue
                                except UserDeactivatedBan as e:
                                    # Handle user deactivation or ban
                                    logging.error(
                                        f"User deactivated or banned: {e}\n\n{chat_url}"
                                    )
                                    await self.message.answer(
                                        f"Користувач деактивований або забанений: {chat_url}",
                                        reply_markup=self.admin_menu,
                                    )
                                    return
                                except Exception as e:
                                    logger.warning(f"Error: {e}\n\n{chat_url}")
                        except UserDeactivatedBan as e:
                            logging.error(
                                f"User deactivated or banned during client initialization: {e}"
                            )
                            await self.message.answer(
                                f"Користувач деактивований або забанений: {self.phone_number}",
                                reply_markup=self.admin_menu,
                            )
                            return
                        except Exception as e:
                            logger.warning(f"Error initializing client: {e}")
                    finally:
                        await orm_update_account(self.phone_number, is_active=False)
                        logging.info(f"Sleep time: {sleep_time}")
                        await asyncio.sleep(sleep_time)

                await self.message.answer(
                    "Ділоги закінчились. Генерую нові...", reply_markup=self.admin_menu
                )
                await continue_dialog(session.prompt, dialogs[:20], session.id, user_ids, self.message)
                await orm_update_session(session_id, is_active=False)
                self.dialog_id += 1

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

    async def send_invite_request(client: Client, chat_url: str):
        # Логіка відправки запиту на запрошення
        # Тут можеш додати код для надсилання запиту або повідомлення адміну каналу
        try:
            # Отправляємо запит на запрошення (якщо це можливо)
            await client.send_message(chat_url, "Запит на приєднання до каналу")
            logging.info(f"Запит на запрошення на канал {chat_url} був надісланий.")
        except Exception as e:
            logging.error(f"Не вдалося надіслати запит на канал {chat_url}: {e}")
            
