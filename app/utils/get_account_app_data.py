import time

from aiogram import Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options


class Form(StatesGroup):
    waiting_for_code = State()


async def auth_proccess(number: str, callback: CallbackQuery, state: FSMContext):
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument(
        f"user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    )

    driver = webdriver.Chrome(options=chrome_options)

    try:
        url = "https://my.telegram.org/auth"
        driver.get(url)
        time.sleep(2)

        phone_field = driver.find_element(By.XPATH, '//*[@id="my_login_phone"]')
        phone_field.send_keys(number)

        time.sleep(2)
        next_btn = driver.find_element(
            By.XPATH, '//*[@id="my_send_form"]/div[2]/button'
        )
        next_btn.click()

        try:
            time.sleep(2)
            too_many_tries = '//*[@id="my_login_alert"]/div'
            if driver.find_element(By.XPATH, too_many_tries):
                await callback.message.answer("Забагато спроб. Спробуйте пізніше.")
                driver.quit()
                return
        except:
            await callback.message.answer("Введіть код для продовження:")
            await Form.waiting_for_code.set()  # Активуємо стан для введення коду
            await state.update_data(
                driver=driver
            )  # Збережемо драйвер для подальшого використання
            
            await process_code(callback.message, state)

    except Exception as e:
        await callback.message.answer(f"Сталася помилка: {e}")
        driver.quit()


async def process_code(message: Message, state: FSMContext):
    code = message.text
    data = await state.get_data()
    driver = data.get("driver")

    try:
        input_form = driver.find_element(By.XPATH, '//*[@id="my_password"]')
        input_form.send_keys(code)

        time.sleep(2)
        support_btn = driver.find_element(
            By.XPATH, '//*[@id="my_login_form"]/div[4]/button'
        )
        support_btn.click()

        time.sleep(2)
        api_dev_tools_btn = driver.find_element(
            By.XPATH, "/html/body/div[2]/div[2]/div/div/div/div/div[2]/div/ul/li[1]/a"
        )
        api_dev_tools_btn.click()

        time.sleep(2)
        title = driver.find_element(By.XPATH, '//*[@id="app_edit_form"]/h2')
        if title and title.text == "App configuration":
            api_id_text = driver.find_element(
                By.XPATH, '//*[@id="app_edit_form"]/div[1]/div[1]/span'
            ).text
            api_hash_text = driver.find_element(
                By.XPATH, '//*[@id="app_edit_form"]/div[2]/div[1]/span'
            ).text

            await message.answer(f"API ID: {api_id_text}\nAPI Hash: {api_hash_text}")
    except Exception as e:
        await message.answer("Помилка при отриманні даних")
        print(f"Error: {e}")
    finally:
        driver.quit()
        await state.finish()
