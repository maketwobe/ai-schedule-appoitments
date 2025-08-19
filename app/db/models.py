from __future__ import annotations
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime, Text
from datetime import datetime

class Base(DeclarativeBase):
    pass

class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(Integer, index=True)
    role: Mapped[str] = mapped_column(String(16))  # user/agent
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

class UserState(Base):
    __tablename__ = "user_state"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(32), index=True)
    # variáveis exigidas
    user_fullname: Mapped[str | None] = mapped_column(String(120))
    user_phone: Mapped[str | None] = mapped_column(String(20))
    user_email: Mapped[str | None] = mapped_column(String(120))
    user_document: Mapped[str | None] = mapped_column(String(20))
    user_birthday_date: Mapped[str | None] = mapped_column(String(10))
    user_token: Mapped[str | None] = mapped_column(Text)
    user_payment_link: Mapped[str | None] = mapped_column(Text)
    doctor_id: Mapped[str | None] = mapped_column(String(20))
    doctor_name: Mapped[str | None] = mapped_column(String(120))
    appoitment_id: Mapped[str | None] = mapped_column(String(80))
    appoitment_date: Mapped[str | None] = mapped_column(String(10))
    appoitment_hour: Mapped[str | None] = mapped_column(String(5))
