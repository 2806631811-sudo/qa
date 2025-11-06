import requests
from typing import List, Dict, Any
from config import FLOWISE_BASE_URL, FLOWISE_API_KEY

def get_all_knowledge_bases() -> List[Dict[str, Any]]:
    """
    调用Flowise API获取所有知识库
    """
    url = f"{FLOWISE_BASE_URL}/api/v1/document-store/store"
    
    headers = {
        "Authorization": f"Bearer {FLOWISE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        if isinstance(data, list):
            return data
        else:
            return []
            
    except requests.exceptions.RequestException as e:
        print(f"调用Flowise知识库API失败: {e}")
        raise Exception(f"获取知识库列表失败: {str(e)}")
    except Exception as e:
        print(f"解析知识库API响应失败: {e}")
        raise Exception(f"解析知识库数据失败: {str(e)}")