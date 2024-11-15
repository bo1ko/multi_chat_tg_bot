from aiogram.types import Message
from pyrogram import Client
from pyrogram.errors import (
    SessionPasswordNeeded,
    FloodWait,
    PhoneCodeInvalid,
    PhoneCodeExpired,
    PasswordHashInvalid
)
import app.database.orm_query as rq
from app.utils.helpers import is_proxy_working


class TelegramLogin:
    def __init__(self, account_managment):
        self.phone_number = None
        self.phone_code_hash = None
        self.app = None
        self.account_managment = account_managment

    async def start_login(self, message: Message, account):
        self.phone_number = account.number
        self.two_code = account.two_auth_code

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
                await message.answer(
                    f"Невалідний проксі {account.proxy} для номера {account.number}",
                    reply_markup=self.account_managment,
                )
                return

            # Check if the proxy is working
            result = await is_proxy_working(proxy)
            if not result:
                await message.answer(
                    f"Помилка при підключенні до Telegram (Проксі не дає відповідь)", reply_markup=self.account_managment
                )
                return
        else:
            proxy = account.proxy

        # Initialize the client if not already connected
        if not self.app or not self.app.is_connected:
            self.app = Client(
                f"sessions/{account.number}",
                api_id=account.api_id,
                api_hash=account.api_hash,
                proxy=proxy,
            )
            await self.app.connect()

        # Send verification code
        try:
            code = await self.app.send_code(account.number)
            self.phone_code_hash = code.phone_code_hash
            await message.answer(
                f"Введи код підтвердження, який отримав на {account.number}", reply_markup=self.account_managment
            )
        except Exception as e:
            await message.answer(f"Не вдалося надіслати код: {str(e)}", reply_markup=self.account_managment)
            await self.app.disconnect()

    async def finish_login(self, message, code_text):
        if not self.phone_number or not self.phone_code_hash:
            await message.answer("Немає збережених даних для авторизації.")
            return

        # Attempt to sign in with the provided code
        try:
            await self.app.sign_in(self.phone_number, self.phone_code_hash, code_text)
            await message.answer("Авторизація успішна!", reply_markup=self.account_managment)
            await rq.orm_change_account_session_status(self.phone_number, True)
        except SessionPasswordNeeded:
            try:
                await self.app.check_password(self.two_code)
                await message.answer("Авторизація 2FA успішна!", reply_markup=self.account_managment)
                await rq.orm_change_account_session_status(self.phone_number, True)
            except PasswordHashInvalid:
                await message.answer("Неправильний пароль 2FA. Спробуйте ще раз.", reply_markup=self.account_managment)
            except Exception as e:
                await message.answer(f"Помилка при перевірці пароля 2FA: {str(e)}", reply_markup=self.account_managment)
        except PhoneCodeInvalid:
            await message.answer("Неправильний код підтвердження. Спробуй ще раз.", reply_markup=self.account_managment)
        except PhoneCodeExpired:
            await message.answer(
                "Код підтвердження закінчився. Спробуй отримати новий код.", reply_markup=self.account_managment
            )
        except FloodWait as e:
            await message.answer(
                f"Тимчасове блокування. Будь ласка, зачекай {e.value} секунд.", reply_markup=self.account_managment
            )
        except Exception as e:
            await message.answer(f"Помилка авторизації: {str(e)}", reply_markup=self.account_managment)
        finally:
            await self.app.disconnect()
