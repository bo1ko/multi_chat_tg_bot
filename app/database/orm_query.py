from sqlalchemy import select, delete, update
from typing import Union

from app.database.engine import engine, session_maker
from app.database.models import Base
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
async def orm_add_account(number: str):
    async with session_maker() as session:
        async with session.begin():
            try:
                obj = Account(number=number)
                session.add(obj)
                await session.commit()
                return obj
            except Exception as e:
                print(e)
                return None