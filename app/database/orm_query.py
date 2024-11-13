from sqlalchemy import select, delete, update
from typing import Union

from app.database.engine import engine, session_maker
from app.database.models import Base, Dialog
from app.database.models import User, Session, Account


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ---------- ADD USER BY ID ----------
async def orm_add_user(tg_id: int, name: str):
    async with session_maker() as session:
        async with session.begin():
            try:
                obj = User(tg_id=tg_id, name=name)
                session.add(obj)
                await session.commit()
                return obj
            except Exception as e:
                print(e)
                return None


# ---------- ADD USER BY NAME ----------
async def orm_add_user_by_name(name: str):
    async with session_maker() as session:
        async with session.begin():
            try:
                obj = User(name=name)
                session.add(obj)
                await session.commit()
                return obj
            except Exception as e:
                print(e)
                return None


# ---------- REMOVE USER ----------
async def orm_remove_user(name: str):
    async with session_maker() as session:
        async with session.begin():
            try:
                query = delete(User).where(User.name == name)
                await session.execute(query)
                await session.commit()
            except Exception as e:
                print(e)
                return None


# ---------- GET USER ----------
async def orm_get_user(
    value: Union[str, int],
    get_by: str = "id",
):
    async with session_maker() as session:
        async with session.begin():
            try:
                if get_by == "id":
                    query = select(User).where(User.tg_id == value)
                elif get_by == "name":
                    query = select(User).where(User.name == value)
                else:
                    return None

                result = await session.execute(query)
                return result.scalar()
            except Exception as e:
                print(e)
                return None


# ---------- GET USERS ----------
async def orm_get_users():
    async with session_maker() as session:
        async with session.begin():
            try:
                query = select(User)
                result = await session.execute(query)
                return result.scalars().all()
            except Exception as e:
                print(e)
                return None


# ---------- IS ADMIN ----------
async def orm_is_admin(tg_id: int):
    async with session_maker() as session:
        async with session.begin():
            try:
                query = select(User).where(User.tg_id == tg_id)
                result = await session.execute(query)
                user = result.scalar()
                return user.is_admin
            except:
                return None


# ---------- ADD ADMIN ----------
async def orm_add_admin(username: str):
    async with session_maker() as session:
        async with session.begin():
            try:
                query = update(User).where(User.name == username).values(is_admin=True)
                await session.execute(query)
                await session.commit()
                return True
            except Exception as e:
                print(e)
                return False


# ---------- REMOVE ADMIN ----------
async def orm_remove_admin(username: str):
    async with session_maker() as session:
        async with session.begin():
            try:
                query = update(User).where(User.name == username).values(is_admin=False)
                await session.execute(query)
                await session.commit()
                return True
            except Exception as e:
                print(e)
                return False


# ---------- GET ALL ADMINS ----------
async def orm_get_all_admins():
    async with session_maker() as session:
        async with session.begin():
            try:
                query = select(User).where(User.is_admin == True)
                result = await session.execute(query)
                admins = result.scalars().all()
                return admins
            except Exception as e:
                print(e)


# ---------- ADD ACCOUNT ----------
async def orm_add_account(number: str, proxy: str, code: str = None):
    async with session_maker() as session:
        async with session.begin():
            try:
                obj = Account(number=number, proxy=proxy, two_auth_code=code)
                session.add(obj)
                await session.commit()
                return obj
            except Exception as e:
                print(e)
                return None


# ---------- GET ALL ACCOUNTS ----------
async def orm_get_all_accounts():
    async with session_maker() as session:
        async with session.begin():
            try:
                query = select(Account)
                result = await session.execute(query)
                accounts = result.scalars().all()
                return accounts
            except Exception as e:
                print(e)
                return None


# ---------- GET ALL WITHOUT AUTHORIZED ACCOUNTS ----------
async def orm_get_all_accounts_without_session():
    async with session_maker() as session:
        async with session.begin():
            try:
                query = select(Account).where(Account.is_app_created == False)
                result = await session.execute(query)
                accounts = result.scalars().all()
                return accounts
            except Exception as e:
                print(e)
                return None

# ---------- GET ALL FREE ACCOUNTS ----------
async def orm_get_free_accounts():    
    async with session_maker() as session:
        async with session.begin():
            try:
                print('!' * 10)
                query = select(Account).where((Account.is_session_created == True) & (Account.is_active == False))
                result = await session.execute(query)
                accounts = result.scalars().all()
                print('!' * 10, accounts)
                return accounts
            except Exception as e:
                print(e)
                return None

# ---------- GET ALL UNAUTHORIZED ACCOUNTS ----------
async def orm_get_authorized_accounts():
    async with session_maker() as session:
        async with session.begin():
            try:
                query = select(Account).where(Account.is_app_created == False)
                result = await session.execute(query)
                accounts = result.scalars().all()
                return accounts
            except Exception as e:
                print(e)
                return None

# ---------- UPDATE SPECIFIC ACCOUNT ----------
async def orm_update_specific_account(id: int, **kwargs):
    async with session_maker() as session:
        async with session.begin():
            try:
                query = update(Account).where(Account.id == id).values(**kwargs)
                await session.execute(query)
                await session.commit()
                return True
            except Exception as e:
                print(e)
                return False

# ---------- GET NOT ACTIVE ACCOUNTS ----------
async def orm_get_not_active_accounts():
    async with session_maker() as session:
        async with session.begin():
            try:
                query = select(Account).where(Account.is_active == False)
                result = await session.execute(query)
                accounts = result.scalars().all()
                return accounts
            except Exception as e:
                print(e)
                return None

# ---------- UPDATE ACCOUNT ----------
async def orm_update_account(number: str, **kwargs):
    async with session_maker() as session:
        async with session.begin():
            try:
                query = update(Account).where(Account.number == number).values(**kwargs)
                await session.execute(query)
                await session.commit()
                return True
            except Exception as e:
                print(e)
                return False

# ---------- UPDATE ACCOUNT BY ID ----------
async def orm_update_account_by_id(id: int, **kwargs):
    async with session_maker() as session:
        async with session.begin():
            try:
                query = update(Account).where(Account.id == id).values(**kwargs)
                await session.execute(query)
                await session.commit()
                return True
            except Exception as e:
                print(e)
                return False

# ---------- GET ALL AUTHORIZED ACCOUNTS ----------
async def orm_get_authorized_accounts_without_session():
    async with session_maker() as session:
        async with session.begin():
            try:
                query = select(Account).where(
                    (Account.is_app_created == True)
                    & (Account.is_session_created == False)
                )
                result = await session.execute(query)
                accounts = result.scalars().all()
                return accounts
            except Exception as e:
                print(e)
                return None


# ---------- GET ACCOUNT ----------
async def orm_get_account(number: str):
    async with session_maker() as session:
        async with session.begin():
            try:
                query = select(Account).where(Account.number == number)
                result = await session.execute(query)
                return result.scalar()
            except Exception as e:
                print(e)
                return None

# ---------- GET ACCOUNT BY ID ----------
async def orm_get_account_by_id(id: int):
    async with session_maker() as session:
        async with session.begin():
            try:
                query = select(Account).where(Account.id == id)
                result = await session.execute(query)
                return result.scalar()
            except Exception as e:
                print(e)
                return None


# ---------- REMOVE ACCOUNT ----------
async def orm_remove_account(number: str):
    async with session_maker() as session:
        async with session.begin():
            try:
                query = delete(Account).where(Account.number == number)
                await session.execute(query)
                await session.commit()
                return True
            except Exception as e:
                print(e)
                return False


# ---------- CHANGE ACCOUNT SESSION STATUS ----------
async def orm_change_account_session_status(number: str, status: bool):
    async with session_maker() as session:
        async with session.begin():
            try:
                query = (
                    update(Account)
                    .where(Account.number == number)
                    .values(is_session_created=status)
                )
                await session.execute(query)
                await session.commit()
                return True
            except Exception as e:
                print(e)
                return False

# ---------- ADD API ----------
async def orm_add_api(number: str, api_id: str, api_hash: str):
    async with session_maker() as session:
        async with session.begin():
            try:
                query = (
                    update(Account)
                    .where(Account.number == number)
                    .values(is_app_created=True, api_id=api_id, api_hash=api_hash)
                )
                await session.execute(query)
                await session.commit()
                return True
            except Exception as e:
                print(e)
                return None


# ---------- SESSION LIST ----------
async def orm_get_all_sessions():
    async with session_maker() as session:
        async with session.begin():
            try:
                query = select(Session)
                result = await session.execute(query)
                sessions = result.scalars().all()
                return sessions
            except Exception as e:
                print(e)
                return None


# ---------- GET SESSION ----------
async def orm_get_session(id: int):
    async with session_maker() as session:
        async with session.begin():
            try:
                query = select(Session).where(Session.id == id)
                result = await session.execute(query)
                return result.scalar()
            except Exception as e:
                print(e)
                return None


# ---------- ADD SESSION ----------
async def orm_add_session(
    session_type: str, data_json: str, chat_url: str, answer_time: str
):
    async with session_maker() as session:
        async with session.begin():
            try:
                obj = Session(
                    session_type=session_type,
                    data=data_json,
                    answer_time=answer_time,
                    chat_url=chat_url,
                )
                session.add(obj)
                await session.commit()
                return obj
            except Exception as e:
                print(e)
                return None

# ---------- REMOVE SESSION ----------
async def orm_remove_session(id: int):
    async with session_maker() as session:
        async with session.begin():
            try:
                query = delete(Session).where(Session.id == id)
                await session.execute(query)
                await session.commit()
                return True
            except Exception as e:
                print(e)
                return False

# ---------- UPDATE SESSION ----------
async def orm_update_session(id: int, **kwargs):
    async with session_maker() as session:
        async with session.begin():
            try:
                query = update(Session).where(Session.id == id).values(**kwargs)
                await session.execute(query)
                await session.commit()
                return True
            except Exception as e:
                print(e)
                return False

# ---------- ADD DIALOG ----------
async def orm_add_dialog(session_id: int, account_id: int, message_id: int, message: str):
    async with session_maker() as session:
        async with session.begin():
            try:
                obj = Dialog(session_id=session_id, account_id=account_id, message_id=message_id, message=message)
                session.add(obj)
                await session.commit()
                return obj
            except Exception as e:
                print(e)
                return None

# ---------- GET DIALOG ----------
async def orm_get_dialogs(session_id: int):
    async with session_maker() as session:
        async with session.begin():
            try:
                query = select(Dialog).where(Dialog.session_id == session_id)
                result = await session.execute(query)
                return result.scalars().all()
            except Exception as e:
                print(e)
                return None
