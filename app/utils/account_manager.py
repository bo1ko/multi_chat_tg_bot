import openpyxl

from app.database.orm_query import orm_add_account, orm_add_proxy, orm_get_account, orm_update_specific_account


async def xlsx_accounts_parser(file_path: str):
    wb = openpyxl.load_workbook(file_path)
    sheet = wb.active
    count = 0

    for row in sheet.iter_rows(min_row=2, min_col=1, max_col=2):
        phone_number = str(row[0].value)
        proxy = str(row[1].value)
        
        print(phone_number, proxy)

        if not phone_number or not proxy:
            continue
        
        try:
            account = await orm_get_account(phone_number)
            
            if account:
                if not account.proxy:
                    update_result = await orm_update_specific_account(account.id, proxy=proxy)
                    
                    if update_result:
                        count += 1
                        
                    continue
                else:
                    continue
            
            result = await orm_add_account(phone_number, proxy)

            if result:
                count += 1

        except Exception as e:
            print(f"Помилка при обробці акаунта {phone_number} з проксі {proxy}: {str(e)}")

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
