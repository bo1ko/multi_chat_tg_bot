from sqlalchemy import (
    JSON,
    DateTime,
    String,
    func,
    Integer,
    Boolean,
    ForeignKey,
    ARRAY,
    BigInteger,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.mutable import MutableList


class Base(DeclarativeBase):
    created: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    updated: Mapped[DateTime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )


class MutableArray(MutableList):
    @classmethod
    def coerce(cls, key, value):
        if not isinstance(value, MutableList):
            value = MutableList(value)
        return super(MutableArray, cls).coerce(key, value)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_type: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    data: Mapped[dict] = mapped_column(JSON, nullable=True)
    chat_url: Mapped[str] = mapped_column(Text, nullable=True)
    answer_time: Mapped[str] = mapped_column(Text, nullable=True)
    is_dialog_created: Mapped[bool] = mapped_column(Boolean, default=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=True)
    
    accounts: Mapped[list] = mapped_column(MutableList.as_mutable(ARRAY(String)), nullable=True)


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    number: Mapped[str] = mapped_column(String(255), unique=True)
    is_app_created: Mapped[bool] = mapped_column(Boolean, default=False)
    api_id: Mapped[str] = mapped_column(Text, nullable=True)
    api_hash: Mapped[str] = mapped_column(Text, nullable=True)
    is_session_created: Mapped[bool] = mapped_column(Boolean, default=False)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    proxy: Mapped[str] = mapped_column(Text, nullable=True)
    two_auth_code: Mapped[str] = mapped_column(Text, nullable=True)



class Dialog(Base):
    __tablename__ = "dialogs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=True
    )
    account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=True
    )
    message_id: Mapped[int] = mapped_column(Integer, nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=True)
