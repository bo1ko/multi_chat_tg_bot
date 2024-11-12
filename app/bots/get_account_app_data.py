from aiogram.types import Message
from playwright.async_api import async_playwright

from app.database.orm_query import orm_get_all_accounts_without_session, orm_add_api

class AuthTgAPI:
    def __init__(self, account_managment):
        self.browser = None
        self.page = None
        self.accounts = []
        self.phone_number = None
        self.current_index = 0  # Поточний індекс акаунта в списку
        self.account_managment = account_managment

    async def initialize_accounts(self):
        # Завантажуємо акаунти з бази даних
        self.accounts = await orm_get_all_accounts_without_session()

    async def start_login(self, message: Message):
        await self.initialize_accounts()
        
        # Перевіряємо, чи є акаунти для обробки
        if not self.accounts:
            await message.answer("Немає акаунтів для авторизації.")
            return

        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=False)
        
        # Починаємо авторизацію з першого акаунта
        await self.process_next_account(message)

    async def process_next_account(self, message: Message):
        if self.current_index >= len(self.accounts):
            await message.answer("Авторизація завершена для всіх акаунтів.", reply_markup=self.account_managment)
            await self.browser.close()
            return

        account = self.accounts[self.current_index]
        self.phone_number = account.number

        # Створюємо нову сторінку для кожного акаунта
        self.page = await self.browser.new_page()
        await self.page.goto("https://my.telegram.org/auth")

        await self.first_step(account, message)

    async def first_step(self, account, message: Message):
        # Заповнюємо номер телефону
        await self.page.fill('//*[@id="my_login_phone"]', account.number)
        await self.page.click('//*[@id="my_send_form"]/div[2]/button')

        try:
            await self.page.wait_for_selector('//*[@id="my_login_alert"]/div', timeout=2000)
            print("Too many tries")
            await message.answer(f"{account.number} - too many tries")
            await self.page.close()
            self.current_index += 1  # Переходимо до наступного акаунта
            await self.process_next_account(message)
        except:
            await message.answer(
                f"Введи код підтвердження, який отримав на {account.number}"
            )

    async def second_step(self, message: Message, code: str):
        try:
            await self.page.fill('//*[@id="my_password"]', code)
            await self.page.click('//*[@id="my_login_form"]/div[4]/button')

            try:
                await self.page.wait_for_selector(
                    '//*[@id="my_login_alert"]/div', timeout=2000
                )
                await message.answer(
                    "Ввели неправильний код підтвердження, спробуйте пізніше знову"
                )
                await self.page.close()
                self.current_index += 1  # Переходимо до наступного акаунта
                await self.process_next_account(message)
            except:
                await self.page.wait_for_selector("xpath=/html/body/div[2]/div[2]/div/div/div/div/div[2]/div/ul/li[1]/a")
                await self.page.click("xpath=/html/body/div[2]/div/div/div/div/div[2]/div/ul/li[1]/a")

                try:
                    api_id, api_hash = await self.get_api_data(self.page)
                    await self.add_api_data_to_account(
                        self.phone_number, api_id, api_hash, message
                    )
                except:
                    await self.create_new_app(self.page, self.phone_number, message)
                await self.page.close()
                self.current_index += 1
                await self.process_next_account(message)
        except Exception as e:
            print("Error during login:", e)
            await message.answer(f"Помилка авторизації 2: {str(e)}")
            await self.page.close()
            self.current_index += 1
            await self.process_next_account(message)

    async def get_api_data(self, page):
        await page.wait_for_selector('//*[@id="app_edit_form"]/h2')
        title = await page.text_content('//*[@id="app_edit_form"]/h2')
        if title == "App configuration":
            api_id_text = await page.text_content(
                '//*[@id="app_edit_form"]/div[1]/div[1]/span'
            )
            api_hash_text = await page.text_content(
                '//*[@id="app_edit_form"]/div[2]/div[1]/span'
            )
            return api_id_text, api_hash_text

    async def create_new_app(self, page, number, message):
        await page.fill('//*[@id="app_title"]', "myapptitle")
        await page.fill('//*[@id="app_shortname"]', "myapptitle")
        await page.click('//*[@id="app_save_btn"]')

        api_id, api_hash = await self.get_api_data(page)
        await self.add_api_data_to_account(number, api_id, api_hash, message)

    async def add_api_data_to_account(
        self, number: str, api_id: str, api_hash: str, message: Message
    ):
        orm_result = await orm_add_api(number, api_id, api_hash)
        if orm_result:
            await message.answer(
                f"API додано до бази даних\nAPI ID: {api_id}\nAPI HASH: {api_hash}"
            )
        else:
            await message.answer(
                f"API не додано до бази даних\nAPI ID: {api_id}\nAPI HASH: {api_hash}"
            )
