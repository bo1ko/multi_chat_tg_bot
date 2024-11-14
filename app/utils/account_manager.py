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

        for row in sheet.iter_rows(min_row=0, min_col=1, max_col=5):
            try:
                phone_number = str(int(row[0].value)) if row[0].value is not None else None
                proxy = str(row[1].value)
                two_code = str(row[2].value) if row[2].value is not None else None
                api_id = str(row[3].value) if row[3].value is not None else None
                api_hash = str(row[4].value) if row[4].value is not None else None
            except Exception as e:
                print(e)
                continue

            if (not phone_number or phone_number == "None") or (not proxy or proxy == "None"):
                continue

            print(phone_number, proxy, two_code, api_id, api_hash)

            try:
                account = await orm_get_account(phone_number)
                print(account)
                if account:
                    continue
                
                if api_id and api_hash:
                    result = await orm_add_account(phone_number, proxy, two_code, api_id, api_hash, is_app_created=True)
                else:
                    result = await orm_add_account(phone_number, proxy, two_code)

                if result:
                    count += 1

            except Exception as e:
                print(f"Помилка при обробці акаунта {phone_number} з проксі {proxy}: {str(e)}")

        return count

    except Exception as e:
        logging.error(f"Помилка при обробці файлу {file_path}: {str(e)}")
        return count
