import ast
import json
import random
import re
import openai
import os
import traceback
import logging
import traceback
import httpx

from aiogram.types import Message, FSInputFile
from aiogram.fsm.context import FSMContext


from app.database.orm_query import (
    orm_add_dialog,
    orm_get_free_accounts,
    orm_get_session,
)
from app.keyboards.inline import get_callback_btns


logger = logging.getLogger(__name__)


def clear_folder(folder_path):
    if os.path.exists(folder_path):
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            if filename != ".gitignore":
                if os.path.isfile(file_path):
                    os.remove(file_path)
                elif os.path.isdir(file_path):
                    os.rmdir(file_path)


async def generate_dialogs(prompt_text, message: Message, back_session_managment):
    prompt_text += """\n\n
    The answer must be in format like this, id values must start from 0:
    [{"message_id":"0", "user_id": "0", "message": "some text"}, {"message_id":"1", "user_id": "1", "message": "some text"}]
    """

    await message.answer("Починаю генерувати відповідь...")

    try:
        client = openai.OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
        )
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt_text},
            ],
            max_tokens=16384,
            temperature=0.7,
        )
        generated_text = completion.choices[0].message.content
        generated_json = extract_json_from_text(generated_text)

        if not generated_json:
            return False

        btns = {"Так": "use_dialog", "Ні": "dont_use_dialog"}

        file_path = "response.txt"
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(str(generated_json[0]))

        file = FSInputFile(file_path, filename="dialogs.txt")

        await message.answer(
            "Ось ваша відповідь в текстовому файлі:",
            reply_markup=back_session_managment,
        )
        await message.answer_document(file)
        await message.answer(
            "Використати даний діалог?", reply_markup=get_callback_btns(btns=btns)
        )

        return str(generated_json[0])

    except openai.OpenAIError as e:
        await message.answer(
            f"Сталася помилка при отриманні відповіді: {e}",
            reply_markup=back_session_managment,
        )


async def continue_dialog(prompt_text, last_dialog, session_id, message: Message):
    prompt_text += f"Based on the prompt above and this dialog, continue the dialog for another 10 messages"
    prompt_text += f"\n\nLast dialog: {last_dialog}"
    prompt_text += """\n\n
    The answer must be in format like this, id values must start from 0:
    [{"message_id":"0", "user_id": "0", "message": "some text"}, {"message_id":"1", "user_id": "1", "message": "some text"}]
    """

    try:
        client = openai.OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
        )
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt_text},
            ],
            max_tokens=16384,
            temperature=0.7,
        )
        generated_text = completion.choices[0].message.content
        generated_json = extract_json_from_text(generated_text)

        if not generated_json:
            return False

        file_path = "contrinue_dialog_response.txt"
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(str(generated_json[0]))

        file = FSInputFile(file_path, filename="next_dialogs.txt")

        await message.answer("Продовження ділогу")
        await message.answer_document(file)

        await orm_

        await roles_distribution(session_id, accounts, str(generated_json[0]))

    except openai.OpenAIError as e:
        logging.error(f"Сталася помилка при отриманні відповіді: {e}")


async def generate_answer_for_user(
    session_id, question, message: Message, back_session_managment
):
    try:
        session = await orm_get_session(session_id)

        if not session:
            await message.answer(
                "Сесія не знаєдена. Не можу дати відповідь користувачеві",
                reply_markup=back_session_managment,
            )
            return

        if session.instructions is None:
            return None

        prompt_text = f"{session.instructions}\n\n"
        prompt_text += f"Question from chat: {question}\n"
        prompt_text += """\n\n
        The answer must be in format like this
        {"message": "some text"}
        """

        try:
            client = openai.OpenAI(
                api_key=os.environ.get("OPENAI_API_KEY"),
            )
            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt_text},
                ],
                max_tokens=16384,
                temperature=0.7,
            )
            generated_text = completion.choices[0].message.content
            json_match = re.search(r"\{.*?\}", generated_text)
            json_text = json_match.group(0)

            try:
                data = json.loads(json_text)  # Парсимо JSON
                answer_text = data.get("message")

                if not answer_text:
                    return False
                else:
                    logging.info("Відповідь користувачеві: " + answer_text)
                    return answer_text

            except json.JSONDecodeError:
                logging.error("Не вдалося розпарсити JSON: " + answer_text)
                return False

        except openai.OpenAIError as e:
            logging.error(f"Сталася помилка при отриманні відповіді: {e}")
    except Exception as e:
        logging.error("helpers.py - generate_answer_for_user()")
        logging.error(f"Сталася помилка при отриманні відповіді: {e}")
        logging.error(traceback.format_exc())
        return False


def extract_json_from_text(text):
    pattern = r"\{.*?\}|\[.*?\]"
    json_matches = re.findall(pattern, text, re.DOTALL)
    json_objects = []

    for match in json_matches:
        try:
            json_obj = json.loads(match)
            # Перевіряємо, чи це список і чи кожен елемент має потрібні ключі
            if isinstance(json_obj, list) and all(
                isinstance(item, dict)
                and {"message_id", "user_id", "message"}.issubset(item.keys())
                for item in json_obj
            ):
                json_objects.append(json_obj)
            else:
                return False
        except json.JSONDecodeError:
            continue

    return json_objects


async def roles_distribution(session_id, accounts, data):
    try:
        data_json = ast.literal_eval(data)

        unique_users = {int(message["user_id"]) for message in data_json}
        print(unique_users)
        print(len(unique_users), len(accounts))
        if len(accounts) < len(unique_users):
            return False, "Недостатньо вільних аккаунтів"
        elif len(accounts) > len(unique_users):
            accounts = accounts[: len(unique_users)]

        result_count = 0
        for message in data_json:
            add_result = await orm_add_dialog(
                session_id,
                accounts[int(message["user_id"])].id,
                int(message["message_id"]),
                message["message"],
            )

            if add_result:
                result_count += 1

        if result_count == len(data_json):
            return True, "Виконано"
        else:
            return False, "Щось пішло не так"
    except Exception as e:
        print(e)
        traceback.format_exc()
        print(traceback.format_exc())
        return False, f"Щось пішло не так\n{e}\n{traceback.format_exc()}"


# random number generator beetwen first and last number
def random_number(first, last):
    return random.randrange(first, last)


def write_unique_message(session_id, text):
    with open(f"answers_log/{session_id}.txt", "a+", encoding="utf-8") as file:
        existing_messages = file.readlines()

        if f"{text}\n" not in existing_messages:
            file.write(f"{text}\n")
            print("Message added to the file.")
            return True
        else:
            print("Message already exists in the file.")
            return False


def clear_unique_message(number):
    with open(f"answers_log/{number}.txt", "w", encoding="utf-8") as file:
        pass


async def is_proxy_working(proxy_url):
    full_proxy_url = f"http://{proxy_url['username']}:{proxy_url['password']}@{proxy_url['hostname']}:{proxy_url['port']}"

    proxies = {"http://": full_proxy_url, "https://": full_proxy_url}

    try:
        logging.warning(f"Використовується проксі: {full_proxy_url}")
        # Use httpx with a timeout to prevent long waits if the proxy isn't responding
        async with httpx.AsyncClient(proxies=proxies, timeout=5) as client:
            # Send a request to a service that returns your IP address
            response = await client.get("https://api.ipify.org")

            if response.status_code == 200:
                logging.warning("Proxy is working. IP:", response.text)
                return True
            else:
                logging.warning(f"Proxy returned status code: {response.status_code}")
    except httpx.HTTPStatusError as e:
        logging.warning(f"HTTP error occurred: {e}")
    except httpx.RequestError as e:
        logging.warning(f"Request error occurred: {e}")
    except Exception as e:
        logging.warning(f"Other error occurred: {e}")

    logging.warning("Proxy is not working.")
    return False
