from sqlalchemy import DateTime, String, func, Integer, Boolean, ForeignKey, ARRAY, BigInteger
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.mutable import MutableList

class Base(DeclarativeBase):
    created: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    updated: Mapped[DateTime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

class MutableArray(MutableList):
    @classmethod
    def coerce(cls, key, value):
        if not isinstance(value, MutableList):
            value = MutableList(value)
        return super(MutableArray, cls).coerce(key, value)

class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
