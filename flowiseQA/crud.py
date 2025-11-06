from sqlalchemy.orm import Session
from sqlalchemy import select, func
from models import QARecord, QAEntity, Conversation
from typing import Tuple, List, Dict, Any
import re
import uuid

# 对话页面相关CRUD操作
def create_conversation(
    db: Session,
    *,
    username: str,
    title: str = "新对话",
    description: str = None,
    conversation_id: str = None
) -> Conversation:
    """
    创建新的对话页面
    """
    if not conversation_id:
        conversation_id = str(uuid.uuid4())
    
    conversation = Conversation(
        conversation_id=conversation_id,
        title=title,
        username=username,
        description=description
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation

def get_conversation_by_id(db: Session, conversation_id: str) -> Conversation | None:
    """
    根据conversation_id获取对话页面
    """
    stmt = select(Conversation).where(
        Conversation.conversation_id == conversation_id,
        Conversation.is_deleted == 0
    )
    return db.scalar(stmt)

def get_conversations_by_username(db: Session, username: str, page: int = 1, size: int = 10) -> Tuple[int, List[Conversation]]:
    """
    获取用户的对话页面列表
    """
    stmt_total = select(func.count(Conversation.id)).where(
        Conversation.username == username,
        Conversation.is_deleted == 0
    )
    total = db.scalar(stmt_total) or 0

    stmt_items = (
        select(Conversation)
        .where(Conversation.username == username, Conversation.is_deleted == 0)
        .order_by(Conversation.updated_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    items = list(db.scalars(stmt_items))
    return total, items

from sqlalchemy.exc import SQLAlchemyError

def update_conversation(
        db: Session,
        conversation_id: str,
        *,
        title: str = None,
        description: str = None,
        is_active: int = None,
        extra: dict = None   # ✅ 新增 extra 参数
) -> bool:
    """
    更新对话页面信息（支持 extra JSON 字段）
    """
    conversation = get_conversation_by_id(db, conversation_id)
    if not conversation:
        return False

    try:
        if title is not None:
            conversation.title = title
        if description is not None:
            conversation.description = description
        if is_active is not None:
            conversation.is_active = is_active
        if extra is not None:
            # ✅ 如果表中的 extra 是 JSON 类型，建议合并而非直接覆盖
            current_extra = conversation.extra or {}
            if isinstance(current_extra, dict):
                current_extra.update(extra)
                conversation.extra = current_extra
            else:
                # 如果不是 dict（极少数情况），直接覆盖
                conversation.extra = extra

        db.commit()
        db.refresh(conversation)
        return True

    except SQLAlchemyError as e:
        db.rollback()
        print(f"❌ 数据库更新失败: {e}")
        return False


def delete_conversation(db: Session, conversation_id: str) -> bool:
    """
    逻辑删除对话页面及其所有相关的QA记录
    """
    conversation = get_conversation_by_id(db, conversation_id)
    if not conversation:
        return False
    
    # 1. 软删除对话页面
    conversation.is_deleted = 1
    
    # 2. 软删除属于该对话页面的所有QA记录
    stmt = select(QARecord).where(
        QARecord.conversation_id == conversation_id,
        QARecord.is_deleted == 0
    )
    qa_records = list(db.scalars(stmt))
    
    for qa_record in qa_records:
        qa_record.is_deleted = 1
    
    db.commit()
    return True

def get_qa_records_by_conversation(db: Session, conversation_id: str, page: int = 1, size: int = 10) -> Tuple[int, List[QARecord]]:
    """
    获取指定对话页面的QA记录
    """
    stmt_total = select(func.count(QARecord.id)).where(
        QARecord.conversation_id == conversation_id,
        QARecord.is_deleted == 0
    )
    total = db.scalar(stmt_total) or 0

    stmt_items = (
        select(QARecord)
        .where(QARecord.conversation_id == conversation_id, QARecord.is_deleted == 0)
        .order_by(QARecord.created_at.asc())  # 对话记录按时间正序排列
        .offset((page - 1) * size)
        .limit(size)
    )
    items = list(db.scalars(stmt_items))
    return total, items

# 修改原有的create_record函数，支持对话页面
def create_record(
    db: Session,
    *,
    username: str,
    question: str,
    answer_raw: str,
    answer_annotated: str,
    chatflow_id: str,
    conversation_id: str = None,
    source_documents: List[Dict[str, Any]] = None
) -> QARecord:
    extra_data = {}
    if source_documents:
        extra_data["source_documents"] = source_documents
    
    rec = QARecord(
        username=username,
        conversation_id=conversation_id,
        question=question,
        answer_raw=answer_raw,
        answer_annotated=answer_annotated,
        chatflow_id=chatflow_id,
        extra=extra_data if extra_data else None
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec

def extract_and_save_entities(db: Session, qa_record_id: int, answer_annotated: str) -> List[QAEntity]:
    """
    从标注答案中提取实体并保存到数据库
    """
    # 使用正则表达式提取 <class>实体</class> 标签中的内容
    entity_pattern = r'<class>(.*?)</class>'
    entities = []
    
    for match in re.finditer(entity_pattern, answer_annotated):
        entity_text = match.group(1).strip()
        start_pos = match.start()
        end_pos = match.end()
        
        # 检查是否已存在相同的实体（避免重复）
        existing = db.scalar(
            select(QAEntity).where(
                QAEntity.qa_record_id == qa_record_id,
                QAEntity.entity_text == entity_text
            )
        )
        
        if not existing:
            entity = QAEntity(
                qa_record_id=qa_record_id,
                entity_text=entity_text,
                start_position=start_pos,
                end_position=end_pos
            )
            db.add(entity)
            entities.append(entity)
    
    if entities:
        db.commit()
        for entity in entities:
            db.refresh(entity)
    
    return entities

def get_entities_by_qa_record(db: Session, qa_record_id: int) -> List[QAEntity]:
    """
    获取指定问答记录的所有实体
    """
    stmt = select(QAEntity).where(QAEntity.qa_record_id == qa_record_id)
    return list(db.scalars(stmt))

def get_entity_by_id(db: Session, entity_id: int) -> QAEntity | None:
    """
    根据ID获取实体
    """
    return db.get(QAEntity, entity_id)

def increment_entity_click_count(db: Session, entity_id: int) -> bool:
    """
    增加实体点击次数
    """
    entity = db.get(QAEntity, entity_id)
    if not entity:
        return False
    
    entity.click_count += 1
    db.commit()
    return True

def update_entity_gstore_cache(db: Session, entity_id: int, gstore_result: Dict[str, Any]) -> bool:
    """
    更新实体的gstore查询结果缓存
    """
    entity = db.get(QAEntity, entity_id)
    if not entity:
        return False
    
    entity.gstore_query_cache = gstore_result
    db.commit()
    return True

def get_history_by_username(db: Session, username: str, page: int, size: int) -> Tuple[int, List[QARecord]]:
    stmt_total = select(func.count(QARecord.id)).where(QARecord.username == username, QARecord.is_deleted == 0)
    total = db.scalar(stmt_total) or 0

    stmt_items = (
        select(QARecord)
        .where(QARecord.username == username, QARecord.is_deleted == 0)
        .order_by(QARecord.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    items = list(db.scalars(stmt_items))
    return total, items

def get_record_by_id(db: Session, rec_id: int) -> QARecord | None:
    return db.get(QARecord, rec_id)

def set_feedback(db: Session, rec_id: int, like: bool) -> bool:
    rec = db.get(QARecord, rec_id)
    if not rec or rec.is_deleted == 1:
        return False
    if like:
        rec.likes += 1
    else:
        rec.dislikes += 1
    db.commit()
    return True

def logical_delete(db: Session, rec_id: int) -> bool:
    rec = db.get(QARecord, rec_id)
    if not rec or rec.is_deleted == 1:
        return False
    rec.is_deleted = 1
    db.commit()
    return True