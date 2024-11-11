import json
import re
import openai
import os

from aiogram.types import Message, FSInputFile

from app.keyboards.inline import get_callback_btns


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
    The answer must be in format like this
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


async def roles_distribution(accounts, json_data): ...
