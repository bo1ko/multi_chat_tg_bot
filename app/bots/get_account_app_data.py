from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
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

    async def start_login(self, message):
        await self.initialize_accounts()

        # Перевіряємо, чи є акаунти для обробки
        if not self.accounts:
            await message.answer("Немає акаунтів для авторизації.")
            return

        # Запуск браузера

        # Починаємо авторизацію з першого акаунта
        await self.process_next_account(message)

    async def process_next_account(self, message):
        self.browser = webdriver.Chrome()
        self.browser.get("https://my.telegram.org/auth")
        
        if self.current_index >= len(self.accounts):
            await message.answer("Авторизація завершена для всіх акаунтів.", reply_markup=self.account_managment)
            self.browser.quit()
            return

        account = self.accounts[self.current_index]
        self.phone_number = account.number

        # Заповнюємо номер телефону
        phone_input = WebDriverWait(self.browser, 10).until(
            EC.presence_of_element_located((By.XPATH, '//*[@id="my_login_phone"]'))
        )
        phone_input.clear()
        phone_input.send_keys(account.number)

        send_button = self.browser.find_element(By.XPATH, '//*[@id="my_send_form"]/div[2]/button')
        send_button.click()

        await self.first_step(account, message)

    async def first_step(self, account, message):
        try:
            # Чекаємо на появу сповіщення про перевищення кількості спроб
            WebDriverWait(self.browser, 5).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="my_login_alert"]/div'))
            )
            await message.answer(f"{account.number} - too many tries")
            self.browser.quit()
            self.current_index += 1  # Переходимо до наступного акаунта
            await self.process_next_account(message)
        except:
            await message.answer(f"Введи код підтвердження, який отримав на {account.number}")

    async def second_step(self, message, code):
        try:
            # Заповнення поля з кодом
            password_input = WebDriverWait(self.browser, 10).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="my_password"]'))
            )
            password_input.clear()
            password_input.send_keys(code)

            login_button = self.browser.find_element(By.XPATH, '//*[@id="my_login_form"]/div[4]/button')
            login_button.click()
            try:
                WebDriverWait(self.browser, 5).until(
                    EC.presence_of_element_located((By.XPATH, '//*[@id="my_login_alert"]/div'))
                )
                await message.answer("Ввели неправильний код підтвердження, спробуйте пізніше знову")
                self.browser.quit()
                self.current_index += 1  # Переходимо до наступного акаунта
                await self.process_next_account(message)
            except:
                # Чекаємо на сторінку після успішного входу
                WebDriverWait(self.browser, 10).until(
                    EC.presence_of_element_located((By.XPATH, "/html/body/div[2]/div[2]/div/div/div/div/div[2]/div/ul/li[1]/a"))
                )
                self.browser.find_element(By.XPATH, "/html/body/div[2]/div[2]/div/div/div/div/div[2]/div/ul/li[1]/a").click()

                try:
                    api_id, api_hash = self.get_api_data()
                    await self.add_api_data_to_account(self.phone_number, api_id, api_hash, message)
                except:
                    await self.create_new_app(message)

                self.browser.quit()
                self.current_index += 1
                await self.process_next_account(message)
        except Exception as e:
            print("Error during login:", e)
            await message.answer(f"Помилка авторизації 2: {str(e)}")
            self.browser.quit()
            self.current_index += 1
            await self.process_next_account(message)

    def get_api_data(self):
        WebDriverWait(self.browser, 10).until(
            EC.presence_of_element_located((By.XPATH, '//*[@id="app_edit_form"]/h2'))
        )
        title = self.browser.find_element(By.XPATH, '//*[@id="app_edit_form"]/h2').text
        if title == "App configuration":
            api_id_text = self.browser.find_element(By.XPATH, '//*[@id="app_edit_form"]/div[1]/div[1]/span').text
            api_hash_text = self.browser.find_element(By.XPATH, '//*[@id="app_edit_form"]/div[2]/div[1]/span').text
            return api_id_text, api_hash_text

    async def create_new_app(self, message):
        app_title = self.browser.find_element(By.XPATH, '//*[@id="app_title"]')
        app_shortname = self.browser.find_element(By.XPATH, '//*[@id="app_shortname"]')
        app_save_button = self.browser.find_element(By.XPATH, '//*[@id="app_save_btn"]')

        app_title.clear()
        app_title.send_keys("myapptitle")
        app_shortname.clear()
        app_shortname.send_keys("myapptitle")
        app_save_button.click()

        api_id, api_hash = self.get_api_data()
        await self.add_api_data_to_account(self.phone_number, api_id, api_hash, message)

    async def add_api_data_to_account(self, number, api_id, api_hash, message):
        orm_result = await orm_add_api(number, api_id, api_hash)
        if orm_result:
            await message.answer(f"API додано до бази даних\nAPI ID: {api_id}\nAPI HASH: {api_hash}")
        else:
            await message.answer(f"API не додано до бази даних\nAPI ID: {api_id}\nAPI HASH: {api_hash}")
