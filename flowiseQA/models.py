from sqlalchemy import Column, BigInteger, Integer, String, Text, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from db import Base
import uuid

class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="新对话")
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # 0/1
    is_deleted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 0/1
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # 关联QA记录
    qa_records: Mapped[list["QARecord"]] = relationship("QARecord", back_populates="conversation", cascade="all, delete-orphan")

class QARecord(Base):
    __tablename__ = "qa_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    conversation_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("conversations.conversation_id"), nullable=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_annotated: Mapped[str] = mapped_column(Text, nullable=False)
    chatflow_id: Mapped[str] = mapped_column(String(64), nullable=False)
    likes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dislikes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_deleted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 0/1
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # 关联实体
    entities: Mapped[list["QAEntity"]] = relationship("QAEntity", back_populates="qa_record", cascade="all, delete-orphan")
    # 关联对话页面
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="qa_records")

class QAEntity(Base):
    __tablename__ = "qa_entities"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    qa_record_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("qa_history.id"), nullable=False)
    entity_text: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    start_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gstore_query_cache: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    click_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # 关联问答记录
    qa_record: Mapped["QARecord"] = relationship("QARecord", back_populates="entities")