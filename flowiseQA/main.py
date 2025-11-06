from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware  # 添加这行
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
from db import Base, engine, SessionLocal
from schemas import (
    QARequest, QAResponse, HistoryResponse, HistoryItem, FeedbackRequest,
    SourceDocument, EntityInfo, EntityClickRequest, EntityQueryResponse,
    ConversationCreateRequest, ConversationUpdateRequest, ConversationInfo,
    ConversationsResponse, ConversationQAResponse, KnowledgeBaseInfo, KnowledgeBasesResponse,
    KnowledgeBaseFile, KnowledgeBaseFilesResponse
)
from flowise_client import call_flowise, call_flowise_full, extract_entities_with_model, get_knowledge_base_by_id, get_all_knowledge_bases
from crud import (
    create_record, get_history_by_username, set_feedback, logical_delete,
    extract_and_save_entities, get_entities_by_qa_record, get_entity_by_id,
    increment_entity_click_count, update_entity_gstore_cache,
    create_conversation, get_conversation_by_id, get_conversations_by_username,
    update_conversation, delete_conversation, get_qa_records_by_conversation
)
from gstore_client import query_entity_nodes
from config import APP_PORT, FLOWISE_CHATFLOW_ID_1,FLOWISE_CHATFLOW_ID_2,FLOWISE_CHATFLOW_ID_3,FLOWISE_CHATFLOW_ID_4

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时建表（不存在则创建）
    Base.metadata.create_all(bind=engine)

    yield

app = FastAPI(title="QA + Entity Extraction Service", version="1.0.0", lifespan=lifespan)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源，生产环境建议限制具体域名
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有HTTP方法
    allow_headers=["*"],  # 允许所有请求头
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/health")
def health():
    return {"status": "ok"}
from config import MERMAID_URL,OLLAMA_URL,OLLAMA_MODEL
import requests  # 确保导入requests库用于调用接口
import json
from typing import Optional


from pydantic import BaseModel
# 意图识别响应模型
class IntentRecognitionResponse(BaseModel):
    intent_id: int  # 1-5的意图ID

@app.post("/qa", response_model=QAResponse)
def qa(req: QARequest, chatflow_id: Optional[str] = None, db: Session = Depends(get_db)):
    # ============ 0) 初始化 overrideConfig ============
    override_config = {}
    if req.conversation_id:
        override_config = {"sessionId": req.conversation_id}
    print(f"=== 初始化overrideConfig ===")
    print(f"overrideConfig: {json.dumps(override_config, ensure_ascii=False)}")
    print(f"传入的 chatflow_id: {chatflow_id}")

    # ============ 0.1) 验证权限 ============
    conversation = None
    if req.conversation_id:
        conversation = get_conversation_by_id(db, req.conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="对话页面不存在")
        if conversation.username != req.username:
            raise HTTPException(status_code=403, detail="无权限访问此对话页面")

    # =====================================================
    # ✅ 1) 检查conversation是否已有intent_id
    # =====================================================
    existing_intent_id = None
    existing_chatflow_id = None
    first_turn = True  # 是否是本会话第一条QA

    if conversation and getattr(conversation, "extra", None):
        extra = conversation.extra or {}
        existing_intent_id = extra.get("intent_id")
        existing_chatflow_id = extra.get("chatflow_id")

        # 判断是否已有QA记录（如果已有则不是第一条）
        from crud import get_qa_records_by_conversation
        total, _ = get_qa_records_by_conversation(db, conversation.conversation_id, 1, 1)
        if total > 0:
            first_turn = False

    # =====================================================
    # ✅ 2) 如果已有intent_id，直接用；否则进行识别
    # =====================================================
    if existing_intent_id and existing_chatflow_id:
        intent_id = existing_intent_id
        flowise_chatflow_id = existing_chatflow_id
        print(f"=== 已存在intent_id={intent_id}，跳过意图识别，使用固定chatflow_id={flowise_chatflow_id} ===")
    else:
        # === 执行意图识别逻辑（保留你原来的那段） ===
        intent_id = None
        try:
            intent_prompt = f"""你是一个严格执行分类任务的机器人。输出要求：
1. 必须输出合法的 JSON 格式，不带任何额外文字；
2. 格式固定为：{{"intent_id": 整数}}；
3. 整数必须是 1、2、3、4 或 5 之一。

意图定义如下（明确边界）：
1. 装备关联与组合推荐：涉及装备之间的搭配、组合、协同使用等问题（如装备A和什么搭配好、装备B与装备C的协同方式）；
2. 后装保障决策支持：涉及后装保障的策略制定、方案选择等决策类问题（如某地区补给方案如何制定、维修优先级决策）；
3. 实时战况：涉及战场实时态势、兵力部署、敌情动态等实时信息查询/分析；
4. 其他后装保障（维修、保养、补给）：涉及具体的维修方法、保养流程、补给操作等执行类问题；
5. 无意义内容（乱码或无效文本）：无法理解的乱码、无实际含义的文本。

示例（覆盖所有意图）：
用户：步枪怎么修？
输出：{{"intent_id": 4}}

用户：坦克和什么装备搭配协同作战好？
输出：{{"intent_id": 1}}

用户：前线部队补给方案怎么选？
输出：{{"intent_id": 2}}

用户：当前敌方坦克的部署位置？
输出：{{"intent_id": 3}}

用户：asdf123乱码文本
输出：{{"intent_id": 5}}

用户问题：{req.question}
请输出结果：
"""

            ollama_response = requests.post(
                url=OLLAMA_URL,
                headers={"Content-Type": "application/json"},
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": intent_prompt,
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.1}
                },
                timeout=10
            )

            raw_response = ollama_response.json()
            response_content = raw_response.get("response", "").strip()
            intent_data = json.loads(response_content)
            intent_id = int(intent_data.get("intent_id", 4))
            print(f"识别意图ID: {intent_id}")

        except Exception as e:
            print(f"意图识别失败: {str(e)}，默认使用意图ID=4")
            intent_id = 4

        intent_to_chatflow = {
            1: FLOWISE_CHATFLOW_ID_1,
            2: FLOWISE_CHATFLOW_ID_2,
            3: FLOWISE_CHATFLOW_ID_3,
            4: FLOWISE_CHATFLOW_ID_4,
            5: FLOWISE_CHATFLOW_ID_4,
        }

        flowise_chatflow_id = intent_to_chatflow.get(intent_id, FLOWISE_CHATFLOW_ID_4)
        print(f"=== 根据意图映射选择Flowise Chatflow ID: {flowise_chatflow_id} ===")

        # ✅ 首次识别后存入conversation.extra
        if conversation:
            conv_extra = conversation.extra or {}
            conv_extra["intent_id"] = intent_id
            conv_extra["chatflow_id"] = flowise_chatflow_id
            update_conversation(db, conversation.conversation_id, extra=conv_extra)
            print(f"已将intent_id={intent_id}写入conversation.extra")

    # =====================================================
    # ✅ 3) 调用 Flowise
    # =====================================================
    flowise_response = call_flowise_full(
        question=req.question,
        override_config=override_config,
        chatflow_id=flowise_chatflow_id
    )
    answer_raw = flowise_response["text"]
    source_documents = flowise_response["source_documents"]

    original_answer_raw = answer_raw
    mermaid_replaced = False

    # ============ 4) 调用 mermaid ============
    try:
        mermaid_response = requests.post(
            url=MERMAID_URL,
            headers={"Content-Type": "application/json"},
            json={"content": answer_raw},
            timeout=5
        )
        if mermaid_response.status_code == 200:
            mermaid_result = mermaid_response.json()
            if (mermaid_result.get("success") is True and isinstance(mermaid_result.get("result"), str)):
                answer_raw = mermaid_result["result"]
                mermaid_replaced = True
                print(f"mermaid替换成功: {mermaid_result.get('message', '无信息')}")
            else:
                print(f"mermaid替换未成功: {mermaid_result.get('message', '未返回原因')}")
        else:
            print(f"mermaid接口返回非200状态码: {mermaid_response.status_code}")
    except Exception as e:
        print(f"mermaid接口调用异常: {str(e)}，使用原始数据")

    # ============ 5) 实体抽取 ============
    if mermaid_replaced:
        answer_annotated = answer_raw
        print("mermaid替换成功，跳过实体抽取")
    else:
        try:
            answer_annotated = extract_entities_with_model(original_answer_raw)
            if not answer_annotated.strip():
                answer_annotated = original_answer_raw
        except Exception as e:
            print(f"实体抽取失败: {e}，使用原始答案")
            answer_annotated = original_answer_raw


    # =====================================================
    # ✅ 5) 仅在首次对话时添加“匹配说明”
    # =====================================================
    intent_description_map = {
        1: "装备关联与组合推荐智能体",
        2: "后装保障决策支持智能体",
        3: "实时战况分析智能体",
        4: "其他后装保障智能体",
        5: "无意义内容处理智能体"
    }

    intent_description = intent_description_map.get(intent_id, "后装保障智能体")

    if first_turn:
        answer_annotated = f"本次对话已为您匹配【{intent_description}】进行处理，以下是具体回答：\n\n{answer_annotated}"
    else:
        print("非首次对话，跳过意图描述添加")

    # =====================================================
    # ✅ 6) 入库（保持原逻辑）
    # =====================================================
    rec = create_record(
        db,
        username=req.username,
        conversation_id=req.conversation_id,
        question=req.question,
        answer_raw=answer_raw,
        answer_annotated=answer_annotated,
        chatflow_id=flowise_chatflow_id,
        source_documents=source_documents,
    )

    # ============ 7) 提取实体 ============
    entities = []
    if not mermaid_replaced:
        try:
            entities = extract_and_save_entities(db, rec.id, answer_annotated)
        except Exception as e:
            print(f"实体保存失败: {e}")

    # ============ 8) 构建响应 ============
    entity_infos = [
        EntityInfo(
            id=entity.id,
            entity_text=entity.entity_text,
            entity_type=entity.entity_type,
            start_position=entity.start_position,
            end_position=entity.end_position,
            click_count=entity.click_count
        )
        for entity in entities
    ]

    return QAResponse(
        id=rec.id,
        username=rec.username,
        conversation_id=rec.conversation_id,
        question=rec.question,
        answer_raw=rec.answer_raw or "",
        answer_annotated=rec.answer_annotated,
        source_documents=[SourceDocument(**doc) for doc in source_documents] if source_documents else [],
        entities=entity_infos
    )




@app.get("/history", response_model=HistoryResponse)
def history(username: str, page: int = 1, size: int = 10, db: Session = Depends(get_db)):
    total, records = get_history_by_username(db, username, page, size)
    items = []
    for r in records:
        source_docs = []
        if r.extra and "source_documents" in r.extra:
            source_docs = [SourceDocument(**doc) for doc in r.extra["source_documents"]]

        # 获取实体信息
        entities = get_entities_by_qa_record(db, r.id)
        entity_infos = [
            EntityInfo(
                id=entity.id,
                entity_text=entity.entity_text,
                entity_type=entity.entity_type,
                start_position=entity.start_position,
                end_position=entity.end_position,
                click_count=entity.click_count
            )
            for entity in entities
        ]

        items.append(HistoryItem(
            id=r.id,
            username=r.username,
            conversation_id=r.conversation_id,
            question=r.question,
            answer_annotated=r.answer_annotated,
            source_documents=source_docs,
            entities=entity_infos,
            created_at=r.created_at
        ))

    return HistoryResponse(total=total, items=items)

@app.post("/entity/query", response_model=EntityQueryResponse)
def query_entity(req: EntityClickRequest, db: Session = Depends(get_db)):
    """
    实体点击查询接口：查询实体相关的知识图谱节点
    """
    # 1) 验证实体是否存在
    entity = get_entity_by_id(db, req.entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="实体不存在")

    # 2) 增加点击次数
    increment_entity_click_count(db, req.entity_id)

    # 3) 检查是否有缓存
    if entity.gstore_query_cache:
        return EntityQueryResponse(
            entity_id=req.entity_id,
            entity_text=entity.entity_text,
            nodes=entity.gstore_query_cache.get("nodes", []),
            relations=entity.gstore_query_cache.get("relations", []),
            cached=True
        )

    # 4) 调用gstore查询
    try:
        gstore_result = query_entity_nodes(req.entity_text)

        # 5) 缓存查询结果
        update_entity_gstore_cache(db, req.entity_id, gstore_result)

        return EntityQueryResponse(
            entity_id=req.entity_id,
            entity_text=entity.entity_text,
            nodes=gstore_result.get("nodes", []),
            relations=gstore_result.get("relations", []),
            cached=False
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"GStore 查询失败: {e}")

@app.post("/feedback")
def feedback(req: FeedbackRequest, db: Session = Depends(get_db)):
    if req.type not in ("like", "dislike"):
        raise HTTPException(status_code=400, detail="type 仅支持 like | dislike")
    ok = set_feedback(db, req.id, like=(req.type == "like"))
    if not ok:
        raise HTTPException(status_code=404, detail="记录不存在或已删除")
    return JSONResponse(content={"status": "ok"})

@app.delete("/qa/{rec_id}")
def delete_record(rec_id: int, db: Session = Depends(get_db)):
    ok = logical_delete(db, rec_id)
    if not ok:
        raise HTTPException(status_code=404, detail="记录不存在或已删除")
    return JSONResponse(content={"status": "ok"})

# 对话页面相关API接口

@app.post("/conversations", response_model=ConversationInfo)
def create_conversation_api(req: ConversationCreateRequest, db: Session = Depends(get_db)):
    """
    创建新的对话页面
    """
    conversation = create_conversation(
        db,
        username=req.username,
        title=req.title,
        description=req.description
    )

    return ConversationInfo(
        id=conversation.id,
        conversation_id=conversation.conversation_id,
        title=conversation.title,
        username=conversation.username,
        description=conversation.description,
        is_active=conversation.is_active,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at
    )

@app.get("/conversations", response_model=ConversationsResponse)
def get_conversations_api(username: str, page: int = 1, size: int = 10, db: Session = Depends(get_db)):
    """
    获取用户的对话页面列表
    """
    total, conversations = get_conversations_by_username(db, username, page, size)

    items = [
        ConversationInfo(
            id=conv.id,
            conversation_id=conv.conversation_id,
            title=conv.title,
            username=conv.username,
            description=conv.description,
            is_active=conv.is_active,
            created_at=conv.created_at,
            updated_at=conv.updated_at
        )
        for conv in conversations
    ]

    return ConversationsResponse(total=total, items=items)

@app.get("/conversations/{conversation_id}", response_model=ConversationInfo)
def get_conversation_api(conversation_id: str, db: Session = Depends(get_db)):
    """
    获取指定对话页面信息
    """
    conversation = get_conversation_by_id(db, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="对话页面不存在")

    return ConversationInfo(
        id=conversation.id,
        conversation_id=conversation.conversation_id,
        title=conversation.title,
        username=conversation.username,
        description=conversation.description,
        is_active=conversation.is_active,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at
    )

@app.put("/conversations/{conversation_id}")
def update_conversation_api(
        conversation_id: str,
        req: ConversationUpdateRequest,
        db: Session = Depends(get_db)
):
    """
    更新对话页面信息
    """
    success = update_conversation(
        db,
        conversation_id,
        title=req.title,
        description=req.description,
        is_active=req.is_active
    )

    if not success:
        raise HTTPException(status_code=404, detail="对话页面不存在")

    return JSONResponse(content={"status": "ok"})

@app.delete("/conversations/{conversation_id}")
def delete_conversation_api(conversation_id: str, db: Session = Depends(get_db)):
    """
    删除对话页面
    """
    success = delete_conversation(db, conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="对话页面不存在")

    return JSONResponse(content={"status": "ok"})

@app.get("/conversations/{conversation_id}/qa", response_model=ConversationQAResponse)
def get_conversation_qa_api(
        conversation_id: str,
        page: int = 1,
        size: int = 10,
        db: Session = Depends(get_db)
):
    """
    获取指定对话页面的QA记录
    """
    # 验证对话页面是否存在
    conversation = get_conversation_by_id(db, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="对话页面不存在")

    total, records = get_qa_records_by_conversation(db, conversation_id, page, size)

    items = []
    for r in records:
        source_docs = []
        if r.extra and "source_documents" in r.extra:
            source_docs = [SourceDocument(**doc) for doc in r.extra["source_documents"]]

        # 获取实体信息
        entities = get_entities_by_qa_record(db, r.id)
        entity_infos = [
            EntityInfo(
                id=entity.id,
                entity_text=entity.entity_text,
                entity_type=entity.entity_type,
                start_position=entity.start_position,
                end_position=entity.end_position,
                click_count=entity.click_count
            )
            for entity in entities
        ]

        items.append(HistoryItem(
            id=r.id,
            username=r.username,
            conversation_id=r.conversation_id,
            question=r.question,
            answer_annotated=r.answer_annotated,
            source_documents=source_docs,
            entities=entity_infos,
            created_at=r.created_at
        ))

    return ConversationQAResponse(
        conversation_id=conversation_id,
        conversation_title=conversation.title,
        total=total,
        items=items
    )

@app.get("/knowledge-bases/{kb_id}/files", response_model=KnowledgeBaseFilesResponse)
def get_knowledge_base_files_api(kb_id: str, page: int = 1, size: int = 10):
    """
    获取指定知识库的文件列表（分页）
    """
    try:
        # 调用Flowise API获取知识库详情
        kb_data = get_knowledge_base_by_id(kb_id)

        if not kb_data:
            raise HTTPException(status_code=404, detail="知识库不存在")

        # 提取所有文件
        all_files = []
        for loader in kb_data.get("loaders", []):
            for file_data in loader.get("files", []):
                all_files.append({
                    "id": file_data.get("id", ""),
                    "name": file_data.get("name", ""),
                    "mimePrefix": file_data.get("mimePrefix", ""),
                    "size": file_data.get("size", 0),
                    "status": file_data.get("status", ""),
                    "uploaded": file_data.get("uploaded", "")
                })

        # 计算分页
        total = len(all_files)
        start_index = (page - 1) * size
        end_index = start_index + size

        # 获取当前页的数据
        page_items = all_files[start_index:end_index]

        # 转换为响应模型
        items = []
        for file_data in page_items:
            try:
                file_info = KnowledgeBaseFile(
                    id=file_data["id"],
                    name=file_data["name"],
                    mimePrefix=file_data["mimePrefix"],
                    size=file_data["size"],
                    status=file_data["status"],
                    uploaded=file_data["uploaded"]
                )
                items.append(file_info)
            except Exception as e:
                print(f"处理文件数据失败: {e}")
                continue

        return KnowledgeBaseFilesResponse(
            total=total,
            knowledge_base_id=kb_data.get("id", ""),
            knowledge_base_name=kb_data.get("name", ""),
            items=items
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"获取知识库文件列表失败: {str(e)}")

@app.get("/knowledge-bases", response_model=KnowledgeBasesResponse)
def get_knowledge_bases_api(page: int = 1, size: int = 10):
    """
    获取知识库列表（分页）
    """
    try:
        # 调用Flowise API获取所有知识库
        all_knowledge_bases = get_all_knowledge_bases()

        # 计算分页
        total = len(all_knowledge_bases)
        start_index = (page - 1) * size
        end_index = start_index + size

        # 获取当前页的数据
        page_items = all_knowledge_bases[start_index:end_index]

        # 转换为响应模型
        items = []
        for kb_data in page_items:
            try:
                # 处理loaders数据
                loaders = []
                for loader_data in kb_data.get("loaders", []):
                    files = []
                    for file_data in loader_data.get("files", []):
                        files.append({
                            "id": file_data.get("id", ""),
                            "name": file_data.get("name", ""),
                            "mimePrefix": file_data.get("mimePrefix", ""),
                            "size": file_data.get("size", 0),
                            "status": file_data.get("status", ""),
                            "uploaded": file_data.get("uploaded", "")
                        })

                    loaders.append({
                        "id": loader_data.get("id", ""),
                        "loaderId": loader_data.get("loaderId", ""),
                        "loaderName": loader_data.get("loaderName", ""),
                        "loaderConfig": loader_data.get("loaderConfig", {}),
                        "splitterId": loader_data.get("splitterId", ""),
                        "splitterName": loader_data.get("splitterName", ""),
                        "splitterConfig": loader_data.get("splitterConfig", {}),
                        "totalChunks": loader_data.get("totalChunks", 0),
                        "totalChars": loader_data.get("totalChars", 0),
                        "status": loader_data.get("status", ""),
                        "files": files,
                        "source": loader_data.get("source", "")
                    })

                # 处理配置数据
                vector_store_config = None
                if kb_data.get("vectorStoreConfig"):
                    vector_store_config = {
                        "config": kb_data["vectorStoreConfig"].get("config", {}),
                        "name": kb_data["vectorStoreConfig"].get("name", "")
                    }

                embedding_config = None
                if kb_data.get("embeddingConfig"):
                    embedding_config = {
                        "config": kb_data["embeddingConfig"].get("config", {}),
                        "name": kb_data["embeddingConfig"].get("name", "")
                    }

                kb_info = KnowledgeBaseInfo(
                    id=kb_data.get("id", ""),
                    name=kb_data.get("name", ""),
                    description=kb_data.get("description", ""),
                    loaders=loaders,
                    whereUsed=kb_data.get("whereUsed", []),
                    createdDate=kb_data.get("createdDate", ""),
                    updatedDate=kb_data.get("updatedDate", ""),
                    status=kb_data.get("status", ""),
                    vectorStoreConfig=vector_store_config,
                    embeddingConfig=embedding_config,
                    recordManagerConfig=kb_data.get("recordManagerConfig"),
                    workspaceId=kb_data.get("workspaceId", ""),
                    totalChars=kb_data.get("totalChars", 0),
                    totalChunks=kb_data.get("totalChunks", 0)
                )
                items.append(kb_info)

            except Exception as e:
                print(f"处理知识库数据失败: {e}")
                continue

        return KnowledgeBasesResponse(total=total, items=items)

    except Exception as e:
        raise HTTPException(status_code=502, detail=f"获取知识库列表失败: {str(e)}")