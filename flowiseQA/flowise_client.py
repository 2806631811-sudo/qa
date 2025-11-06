
import requests
from typing import Optional, Dict, List, Any
from config import FLOWISE_BASE_URL, FLOWISE_CHATFLOW_ID, FLOWISE_API_KEY
import json

def _headers_json():
    headers = {"Content-Type": "application/json"}
    if FLOWISE_API_KEY:
        headers["Authorization"] = f"Bearer {FLOWISE_API_KEY}"
    return headers

def _extract_text(resp_json) -> str:
    if resp_json is None:
        return ""
    if isinstance(resp_json, str):
        return resp_json
    for key in ["text", "answer", "result", "message"]:
        if key in resp_json and isinstance(resp_json[key], str):
            return resp_json[key]
    if "data" in resp_json and isinstance(resp_json["data"], dict):
        for key in ["text", "answer", "result"]:
            if key in resp_json["data"] and isinstance(resp_json["data"][key], str):
                return resp_json["data"][key]
    return str(resp_json)

def _extract_source_documents(resp_json) -> List[Dict[str, Any]]:
    if resp_json is None or not isinstance(resp_json, dict):
        return []
    source_docs = resp_json.get("sourceDocuments", [])
    return source_docs if isinstance(source_docs, list) else []

def _call_flowise_api(
        question: str,
        override_config: Optional[Dict[str, Any]] = None,
        is_entity_extract: bool = False,  # 新增：标记是否是实体抽取请求
        chatflow_id: Optional[str] = None  # 新增：传递chatflow_id
) -> dict:
    # 使用传入的chatflow_id，若没有则使用默认的FLOWISE_CHATFLOW_ID
    effective_chatflow_id = chatflow_id or FLOWISE_CHATFLOW_ID
    url = f"{FLOWISE_BASE_URL}/api/v1/prediction/{effective_chatflow_id}"

    payload = {
        "question": question,
        "overrideConfig": override_config or {}
    }

    # 打印日志时区分请求类型，避免混淆
    if is_entity_extract:
        print(f"=== 实体抽取：发送给Flowise的请求体 ===")
    else:
        print(f"=== 用户问答：发送给Flowise的请求体 ===")

    print(f"请求URL: {url}")
    print(f"请求体: {json.dumps(payload, ensure_ascii=False, indent=2)}")
    print("===========================")

    resp = requests.post(url, json=payload, headers=_headers_json(), timeout=60)
    resp.raise_for_status()
    return resp.json()

# 修改call_flowise和call_flowise_full，使其支持传递chatflow_id参数

def call_flowise(
        question: str,
        override_config: Optional[Dict[str, Any]] = None,
        chatflow_id: Optional[str] = None  # 新增：传递chatflow_id
) -> str:
    resp_json = _call_flowise_api(question, override_config, is_entity_extract=False, chatflow_id=chatflow_id)
    return _extract_text(resp_json)

def call_flowise_full(
        question: str,
        override_config: Optional[Dict[str, Any]] = None,
        chatflow_id: Optional[str] = None  # 新增：传递chatflow_id
) -> Dict[str, Any]:
    resp_json = _call_flowise_api(question, override_config, is_entity_extract=False, chatflow_id=chatflow_id)
    return {
        "text": _extract_text(resp_json),
        "source_documents": _extract_source_documents(resp_json),
        "override_config": override_config
    }



# 3. 实体抽取调用（新增传递overrideConfig）
def extract_entities_with_model(
        answer_text: str,
        override_config: Optional[Dict[str, Any]] = None  # 新增：传递overrideConfig
) -> str:
    prompt = build_entity_extraction_prompt(answer_text)
    # 调用时传入overrideConfig，确保实体抽取请求也携带sessionId
    return call_flowise(prompt, override_config=override_config)

# 构建实体抽取Prompt（保持不变）
def build_entity_extraction_prompt(answer_text: str) -> str:
    return (
        "请对下面的文本进行命名实体抽取，严格按照以下要求：\n"
        "1) 保留原文本的完整顺序和内容，不删除任何信息；\n"
        "2) 识别所有实体（人名、地名、组织、时间、数值、产品、技术术语、概念等）；\n"
        "3) 将每个实体用 <class>实体内容</class> 标签包裹，注意标签格式必须严格一致；\n"
        "4) 禁止输出解释、标题或其他多余文字；\n"
        "5) 仅返回标注后的文本内容。\n\n"
        "示例格式：<class>COT</class> 是一种 <class>机器学习</class> 方法。\n\n"
        f"待处理文本：\n{answer_text}\n\n"
        "标注结果："
    )

# 知识库相关函数（保持不变）
def get_all_knowledge_bases() -> List[Dict[str, Any]]:
    url = f"{FLOWISE_BASE_URL}/api/v1/document-store/store"
    headers = {"Authorization": f"Bearer {FLOWISE_API_KEY}", "Content-Type": "application/json"}
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"获取知识库列表失败: {e}")
        raise Exception(f"获取知识库列表失败: {str(e)}")

def get_knowledge_base_by_id(kb_id: str) -> Dict[str, Any]:
    url = f"{FLOWISE_BASE_URL}/api/v1/document-store/store/{kb_id}"
    headers = {"Authorization": f"Bearer {FLOWISE_API_KEY}", "Content-Type": "application/json"}
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f"获取知识库详情失败: {e}")
        raise Exception(f"获取知识库详情失败: {str(e)}")