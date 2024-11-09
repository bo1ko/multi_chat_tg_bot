from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from pyrogram import Client
from pyrogram.errors import SessionPasswordNeeded, FloodWait, PhoneCodeInvalid, PhoneCodeExpired

import app.database.orm_query as rq


class TelegramLogin:
    def __init__(self):
        self.phone_number = None
        self.phone_code_hash = None
        self.app = None
        self.accounts = []  # Список акаунтів для авторизації
        self.current_index = 0  # Поточний індекс акаунта в списку

    async def initialize_accounts(self):
        self.accounts = await rq.orm_get_authorized_accounts_without_session()

    async def start_login(self, message: Message, state: FSMContext):
        await self.initialize_accounts()
        
        # Перевіряємо, чи є акаунти для обробки
        if not self.accounts:
            await message.answer("Немає акаунтів для авторизації.")
            return

        # Починаємо авторизацію з першого акаунта
        await self.process_next_account(message)

    async def process_next_account(self, message: Message):
        if self.current_index >= len(self.accounts):
            await message.answer("Авторизація завершена для всіх акаунтів.")
            return

        account = self.accounts[self.current_index]
        self.phone_number = account.number
        

        # Створюємо новий клієнт, якщо необхідно
        if not self.app or not self.app.is_connected:
            self.app = Client(f"sessions/{account.number}", api_id=account.api_id, api_hash=account.api_hash)
            await self.app.connect()

        try:
            code = await self.app.send_code(account.number)
            self.phone_code_hash = code.phone_code_hash

            await message.answer(f"Введи код підтвердження, який отримав на {account.number}")
        except Exception as e:
            await message.answer(f"Не вдалося надіслати код: {str(e)}")
            self.current_index += 1
            await self.process_next_account(message)  # Переходимо до наступного акаунта

    async def finish_login(self, message, code_text):
        if not self.phone_number or not self.phone_code_hash:
            await message.answer("Немає збережених даних для авторизації.")
            return

        try:
            await self.app.sign_in(self.phone_number, self.phone_code_hash, code_text)
            await message.answer("Авторизація успішна!")
            await rq.orm_change_account_session_status(self.phone_number, True)
        except SessionPasswordNeeded:
            await message.answer("Потрібен пароль для двоетапної авторизації. Введи пароль.")
        except PhoneCodeInvalid:
            await message.answer("Неправильний код підтвердження. Спробуй ще раз.")
        except PhoneCodeExpired:
            await message.answer("Код підтвердження закінчився. Спробуй отримати новий код.")
        except FloodWait as e:
            await message.answer(f"Тимчасове блокування. Будь ласка, зачекай {e.value} секунд.")
        except Exception as e:
            await message.answer(f"Помилка авторизації: {str(e)}")
        finally:
            await self.app.disconnect()
            self.current_index += 1  # Переходимо до наступного акаунта
            await self.process_next_account(message)  # Запускаємо наступний акаунт
