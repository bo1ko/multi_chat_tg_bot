import traceback
import time

from aiogram.types import Message
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

from app.database.orm_query import orm_get_all_accounts_without_session, orm_add_api


class AuthTgAPI:
    def __init__(self):
        self.driver = None
        self.accounts = []
        self.current_index = 0

    async def initialize_accounts(self):
        self.accounts = await orm_get_all_accounts_without_session()

    async def start_login(self, message: Message):
        await self.initialize_accounts()

        if not self.accounts:
            await message.answer("Немає акаунтів для авторизації.")
            return

        await self.first_step(message)

    async def first_step(self, message: Message):
        if self.current_index >= len(self.accounts):
            await message.answer("Авторизація завершена для всіх акаунтів.")
            return

        account = self.accounts[self.current_index]

        chrome_options = Options()
        # chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        self.driver = webdriver.Chrome(options=chrome_options)

        url = "https://my.telegram.org/auth"
        self.driver.get(url)

        time.sleep(2)
        phone_field = self.driver.find_element(By.XPATH, '//*[@id="my_login_phone"]')
        phone_field.send_keys(account.number)

        time.sleep(2)
        next_btn = self.driver.find_element(
            By.XPATH, '//*[@id="my_send_form"]/div[2]/button'
        )
        next_btn.click()

        try:
            time.sleep(2)
            too_many_tries = '//*[@id="my_login_alert"]/div'
            if self.driver.find_element(By.XPATH, too_many_tries):
                print("Too many tries")
                self.current_index += 1
                self.driver.quit()
                await message.answer(f"{account.number} - too many tries")
                await self.first_step(message)
        except Exception as e:
            print(traceback.format_exc())

            try:
                await message.answer(
                    f"Введи код підтвердження, який отримав на {account.number}"
                )
            except Exception as e:
                await message.answer(f"Не вдалося надіслати код: {str(e)}")
                self.current_index += 1
                await self.process_next_account(message)

    async def second_step(self, message: Message, code: str):
        try:
            time.sleep(2)
            input_form = self.driver.find_element(By.XPATH, '//*[@id="my_password"]')
            input_form.send_keys(code)

            time.sleep(2)
            support_btn = self.driver.find_element(
                By.XPATH, '//*[@id="my_login_form"]/div[4]/button'
            )
            support_btn.click()

            time.sleep(2)
            api_dev_tools_btn = self.driver.find_element(
                By.XPATH,
                "/html/body/div[2]/div[2]/div/div/div/div/div[2]/div/ul/li[1]/a",
            )
            api_dev_tools_btn.click()

            number = self.accounts[self.current_index].number

            try:
                api_id, api_hash = self.get_api_data()
                await self.add_api_data_to_account(number, api_id, api_hash, message)
            except:
                try:
                    time.sleep(2)
                    create_title = self.driver.find_element(
                        By.XPATH, '//*[@id="app_create_form"]/h2'
                    )

                    if create_title:
                        if create_title.text == "Create new application":
                            app_title_form = self.driver.find_element(
                                By.XPATH, '//*[@id="app_title"]'
                            )
                            app_title_form.send_keys("myapptitle")

                            app_short_title = self.driver.find_element(
                                By.XPATH, '//*[@id="app_shortname"]'
                            )
                            app_short_title.send_keys("myapptitle")

                            create_btn = self.driver.find_element(
                                By.XPATH, '//*[@id="app_save_btn"]'
                            )
                            create_btn.click()

                            api_id, api_hash = self.get_api_data()
                            await self.add_api_data_to_account(
                                number, api_id, api_hash, message
                            )

                except Exception as e:
                    print("Error wrapper", e)
                    await message.answer(f"Помилка авторизації 1: {str(e)}")
        except Exception as e:
            print("Error inner", e)
            await message.answer(f"Помилка авторизації 2: {str(e)}")
        finally:
            self.driver.quit()
            self.current_index += 1
            await self.first_step(message)

    def get_api_data(self):
        time.sleep(2)
        title = self.driver.find_element(By.XPATH, '//*[@id="app_edit_form"]/h2')
        if title:
            if title.text == "App configuration":
                api_id_el = '//*[@id="app_edit_form"]/div[1]/div[1]/span'
                api_id_text = self.driver.find_element(By.XPATH, api_id_el).text

                api_hash_el = '//*[@id="app_edit_form"]/div[2]/div[1]/span'
                api_hash_text = self.driver.find_element(By.XPATH, api_hash_el).text

                return api_id_text, api_hash_text

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
