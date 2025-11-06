from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# 对话页面相关模型
class ConversationCreateRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    title: str = Field(default="新对话", max_length=255)
    description: Optional[str] = None

class ConversationUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    is_active: Optional[int] = Field(None, ge=0, le=1)

class ConversationInfo(BaseModel):
    id: int
    conversation_id: str
    title: str
    username: str
    description: Optional[str] = None
    is_active: int
    created_at: datetime
    updated_at: datetime

class ConversationsResponse(BaseModel):
    total: int
    items: List[ConversationInfo]

# 修改QA请求模型，支持对话页面
class QARequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    question: str = Field(..., min_length=1)
    conversation_id: Optional[str] = None  # 可选的对话页面ID
    chatflow_id: Optional[str] = None


class SourceDocument(BaseModel):
    pageContent: str
    metadata: Dict[str, Any]

class EntityInfo(BaseModel):
    id: int
    entity_text: str
    entity_type: Optional[str] = None
    start_position: Optional[int] = None
    end_position: Optional[int] = None
    click_count: int = 0

# 修改QA响应模型，包含对话页面信息
class QAResponse(BaseModel):
    id: int
    username: str
    conversation_id: Optional[str] = None
    question: str
    answer_raw: str
    answer_annotated: str
    source_documents: List[SourceDocument] = []
    entities: List[EntityInfo] = []

# 修改历史记录项模型
class HistoryItem(BaseModel):
    id: int
    username: str
    conversation_id: Optional[str] = None
    question: str
    answer_annotated: str
    source_documents: List[SourceDocument] = []
    entities: List[EntityInfo] = []
    created_at: datetime

class HistoryResponse(BaseModel):
    total: int
    items: List[HistoryItem]

# 对话页面的QA记录响应
class ConversationQAResponse(BaseModel):
    conversation_id: str
    conversation_title: str
    total: int
    items: List[HistoryItem]

class FeedbackRequest(BaseModel):
    id: int
    type: str  # like | dislike

# 实体点击查询相关模型
class EntityClickRequest(BaseModel):
    entity_id: int
    entity_text: str = Field(..., min_length=1)

class GStoreNode(BaseModel):
    id: str
    label: str
    properties: Dict[str, Any] = {}

class GStoreRelation(BaseModel):
    source: str
    target: str
    relation: str
    properties: Dict[str, Any] = {}

class EntityQueryResponse(BaseModel):
    entity_id: int
    entity_text: str
    nodes: List[GStoreNode] = []
    relations: List[GStoreRelation] = []
    cached: bool = False  # 是否来自缓存

# 知识库相关模型
class KnowledgeBaseFile(BaseModel):
    id: str
    name: str
    mimePrefix: str
    size: int
    status: str
    uploaded: str

class KnowledgeBaseLoader(BaseModel):
    id: str
    loaderId: str
    loaderName: str
    loaderConfig: Dict[str, Any]
    splitterId: str
    splitterName: str
    splitterConfig: Dict[str, Any]
    totalChunks: int
    totalChars: int
    status: str
    files: List[KnowledgeBaseFile]
    source: str

class VectorStoreConfig(BaseModel):
    config: Dict[str, Any]
    name: str

class EmbeddingConfig(BaseModel):
    config: Dict[str, Any]
    name: str

class KnowledgeBaseInfo(BaseModel):
    id: str
    name: str
    description: str
    loaders: List[KnowledgeBaseLoader]
    whereUsed: List[str]
    createdDate: str
    updatedDate: str
    status: str
    vectorStoreConfig: Optional[VectorStoreConfig] = None
    embeddingConfig: Optional[EmbeddingConfig] = None
    recordManagerConfig: Optional[Dict[str, Any]] = None
    workspaceId: str
    totalChars: int
    totalChunks: int

class KnowledgeBasesResponse(BaseModel):
    total: int
    items: List[KnowledgeBaseInfo]

class KnowledgeBaseFilesResponse(BaseModel):
    total: int
    knowledge_base_id: str
    knowledge_base_name: str
    items: List[KnowledgeBaseFile]