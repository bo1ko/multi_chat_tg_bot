import openpyxl
import logging

from app.database.orm_query import (
    orm_add_account,
    orm_get_account,
    orm_update_specific_account,
)

logger = logging.getLogger(__name__)


async def xlsx_accounts_parser(file_path: str):
    try:
        wb = openpyxl.load_workbook(file_path)
        sheet = wb.active
        count = 0

        for row in sheet.iter_rows(min_row=2, min_col=1, max_col=2):
            phone_number = str(int(float(row[0].value)))
            proxy = str(row[1].value)

            if not phone_number or not proxy or proxy == "None":
                continue

            print(phone_number, proxy)

            try:
                account = await orm_get_account(phone_number)

                if account:
                    continue

                result = await orm_add_account(phone_number, proxy)

                if result:
                    count += 1

            except Exception as e:
                print(
                    f"Помилка при обробці акаунта {phone_number} з проксі {proxy}: {str(e)}"
                )

        return count
    except Exception as e:
        logging.error(f"Помилка при обробці файлу {file_path}: {str(e)}")
        return False
