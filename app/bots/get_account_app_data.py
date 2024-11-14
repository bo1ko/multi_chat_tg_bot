import asyncio
import random
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
        self.page = await self.browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        )

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
                await message.answer(
                    f"Введи код підтвердження, який отримав на {account.number}"
                )
        except Exception as e:
            await message.answer(f"Помилка на етапі 1: {str(e)}")
            await self.close_browser()

    async def second_step(self, message, code):
        print("!" * 10, "Запущеноa")
        try:
            # Вводимо код підтвердження
            await self.page.fill('//*[@id="my_password"]', code)
            await self.page.click('//*[@id="my_login_form"]/div[4]/button')

            await asyncio.sleep(2)

            if await self.page.is_visible('//*[@id="my_login_alert"]/div'):
                await message.answer(
                    "Ввели неправильний код підтвердження, спробуйте пізніше знову"
                )
                await self.close_browser()
            else:
                # Перевіряємо успішний вхід та переходимо до отримання API даних
                await self.page.wait_for_selector(
                    "xpath=/html/body/div[2]/div[2]/div/div/div/div/div[2]/div/ul/li[1]/a"
                )
                await self.page.click(
                    "xpath=/html/body/div[2]/div[2]/div/div/div/div/div[2]/div/ul/li[1]/a"
                )

                await asyncio.sleep(2)

                try:
                    create_title = await self.page.wait_for_selector(
                        "#app_create_form > h2", timeout=5000
                    )

                    if create_title:
                        create_title_text = await create_title.text_content()

                        if create_title_text == "Create new application":
                            await self.create_new_app(message)
                    else:
                        api_id, api_hash = await self.get_api_data()
                        await self.add_api_data_to_account(
                            self.phone_number, api_id, api_hash, message
                        )
                except:
                    api_id, api_hash = await self.get_api_data()
                    await self.add_api_data_to_account(
                        self.phone_number, api_id, api_hash, message
                    )

        except Exception as e:
            await message.answer(f"Помилка авторизації 2: {str(e)}")
            await self.close_browser()

    async def get_api_data(self):
        # Отримуємо дані API ID та API HASH
        await self.page.wait_for_selector('//*[@id="app_edit_form"]/h2')
        title = await self.page.inner_text('//*[@id="app_edit_form"]/h2')
        if title == "App configuration":
            api_id_text = await self.page.inner_text(
                '//*[@id="app_edit_form"]/div[1]/div[1]/span'
            )
            api_hash_text = await self.page.inner_text(
                '//*[@id="app_edit_form"]/div[2]/div[1]/span'
            )
            return api_id_text, api_hash_text

    async def create_new_app(self, message):
        # Retry counter
        retries = 5
        attempt = 0

        # Initial app title and shortname
        app_title = "myapptitle"
        app_shortname = "myapptitle"

        while attempt < retries:
            attempt += 1

            # Fill in app title and shortname
            await asyncio.sleep(1)
            await self.page.fill('//*[@id="app_title"]', app_title)
            await asyncio.sleep(1)
            await self.page.fill('//*[@id="app_shortname"]', app_shortname)
            await asyncio.sleep(1)
            await self.page.click(
                '//*[@id="app_create_form"]/div[4]/div/div[1]/label/input'
            )
            await asyncio.sleep(1)
            await self.page.click('//*[@id="app_save_btn"]')

            await asyncio.sleep(2)  # Give time for the URL to potentially change

            # If the URL hasn't changed, refresh and update the app title
            try:
                await self.page.wait_for_selector(
                    '//*[@id="app_edit_form"]/h2', timeout=1000
                )
                break
            except:
                print(
                    f"Attempt {attempt}: URL hasn't changed, refreshing and retrying with a new title."
                )

                # Refresh the page
                await self.page.reload()

                # Generate a new app title with random digits
                app_title = f"myapptitle{random.randint(1000, 9999)}"
                app_shortname = f"myapptitle"

                # Wait a moment after refresh before retrying
                await asyncio.sleep(2)
                # If URL has changed, break out of the loop

        # After retries or success, proceed with API data
        api_id, api_hash = await self.get_api_data()
        await self.add_api_data_to_account(self.phone_number, api_id, api_hash, message)

    async def add_api_data_to_account(self, number, api_id, api_hash, message):
        orm_result = await orm_add_api(number, api_id, api_hash)
        if orm_result:
            await message.answer(
                f"API додано до бази даних\nAPI ID: {api_id}\nAPI HASH: {api_hash}"
            )
        else:
            await message.answer(
                f"API не додано до бази даних\nAPI ID: {api_id}\nAPI HASH: {api_hash}"
            )

        await self.close_browser()
