import openpyxl

from app.database.orm_query import orm_add_account, orm_add_proxy


async def xlsx_accounts_parser(file_path: str):
    wb = openpyxl.load_workbook(file_path)
    sheet = wb.active
    count = 0

    for row in sheet.iter_rows(min_row=2, min_col=1, max_col=1):
        for cell in row:
            result = await orm_add_account(str(int(cell.value)))

            if result:
                count += 1

    return count


async def xlsx_proxies_parser(file_path: str):
    wb = openpyxl.load_workbook(file_path)
    sheet = wb.active
    count = 0

    for row in sheet.iter_rows(min_row=2, min_col=1, max_col=1):
        for cell in row:
            result = await orm_add_proxy(cell.value)

            if result:
                count += 1

    return count
