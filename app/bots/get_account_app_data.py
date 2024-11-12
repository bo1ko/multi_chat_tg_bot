import asyncio
from playwright.async_api import async_playwright
from app.database.orm_query import orm_add_api

class AuthTgAPI:
    def __init__(self, account_managment):
        self.account_managment = account_managment
        self.browser = None
        self.page = None
        self.playwright = None

    async def initialize_browser(self):
        # Ініціалізуємо playwright і браузер
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=False)
        self.page = await self.browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")

    async def close_browser(self):
        # Закриваємо браузер і playwright
        if self.page:
            await self.page.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def start_login(self, message, account):
        try:
            # Перевіряємо чи браузер ініціалізовано
            if not self.browser or not self.page:
                await self.initialize_browser()
            
            # Переходимо на сторінку авторизації
            await self.page.goto("https://my.telegram.org/auth")
            self.phone_number = account.number

            # Заповнюємо номер телефону
            await self.page.fill('//*[@id="my_login_phone"]', account.number)
            await self.page.click('//*[@id="my_send_form"]/div[2]/button')
            await asyncio.sleep(2)
        
            if await self.page.is_visible('//*[@id="my_login_alert"]/div'):
                await message.answer(f"{account.number} - too many tries")
                await self.close_browser()
            else:
                await message.answer(f"Введи код підтвердження, який отримав на {account.number}")
        except Exception as e:
            await message.answer(f"Помилка на етапі 1: {str(e)}")
            await self.close_browser()

    async def second_step(self, message, code):
        try:
            # Вводимо код підтвердження
            await self.page.fill('//*[@id="my_password"]', code)
            await self.page.click('//*[@id="my_login_form"]/div[4]/button')

            await asyncio.sleep(2)
            
            if await self.page.is_visible('//*[@id="my_login_alert"]/div'):
                await message.answer("Ввели неправильний код підтвердження, спробуйте пізніше знову")
                await self.close_browser()
            else:
                # Перевіряємо успішний вхід та переходимо до отримання API даних
                await self.page.wait_for_selector("/html/body/div[2]/div[2]/div/div/div/div/div[2]/div/ul/li[1]/a")
                await self.page.click("/html/body/div[2]/div[2]/div/div/div/div/div[2]/div/ul/li[1]/a")

                await asyncio.sleep(2)
                
                try:
                    api_id, api_hash = await self.get_api_data()
                    await self.add_api_data_to_account(
                        self.phone_number, api_id, api_hash, message
                    )
                except:
                    await self.create_new_app(self.page, self.phone_number, message)
        except Exception as e:
            await message.answer(f"Помилка авторизації 2: {str(e)}")
            await self.close_browser()

    async def get_api_data(self):
        # Отримуємо дані API ID та API HASH
        await self.page.wait_for_selector('//*[@id="app_edit_form"]/h2')
        title = await self.page.inner_text('//*[@id="app_edit_form"]/h2')
        if title == "App configuration":
            api_id_text = await self.page.inner_text('//*[@id="app_edit_form"]/div[1]/div[1]/span')
            api_hash_text = await self.page.inner_text('//*[@id="app_edit_form"]/div[2]/div[1]/span')
            return api_id_text, api_hash_text

    async def create_new_app(self, message):
        # Створюємо новий додаток, якщо немає існуючого API
        await self.page.fill('//*[@id="app_title"]', "myapptitle")
        await self.page.fill('//*[@id="app_shortname"]', "myapptitle")
        await self.page.click('//*[@id="app_save_btn"]')

        await asyncio.sleep(2)
        
        api_id, api_hash = await self.get_api_data()
        await self.add_api_data_to_account(self.phone_number, api_id, api_hash, message)

    async def add_api_data_to_account(self, number, api_id, api_hash, message):
        orm_result = await orm_add_api(number, api_id, api_hash)
        if orm_result:
            await message.answer(f"API додано до бази даних\nAPI ID: {api_id}\nAPI HASH: {api_hash}")
        else:
            await message.answer(f"API не додано до бази даних\nAPI ID: {api_id}\nAPI HASH: {api_hash}")
