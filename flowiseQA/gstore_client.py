import requests
from typing import Dict, List, Any, Optional
from config import GSTORE_BASE_URL, GSTORE_USERNAME, GSTORE_PASSWORD, GSTORE_DB_NAME
import json
import logging

# 配置日志
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def _get_gstore_headers():
    """获取gstore请求头"""
    return {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

def query_entity_nodes(entity_text: str) -> Dict[str, Any]:
    """
    查询实体相关的节点和关系 - 通用版本
    
    Args:
        entity_text: 实体文本
        
    Returns:
        包含nodes和relations的字典
    """
    print(f"\n=== SPARQL查询开始 ===")
    print(f"查询实体: '{entity_text}'")
    
    logger.info(f"开始查询实体: {entity_text}")
    
    try:
        # 转义实体文本，防止SPARQL注入
        escaped_entity_text = entity_text.replace('"', '\\"').replace("'", "\\'")
        print(f"转义后实体: '{escaped_entity_text}'")
        logger.debug(f"转义后的实体文本: {escaped_entity_text}")
        
        # 构建通用的SPARQL查询语句
        sparql_query = f"""
        SELECT DISTINCT ?subject ?predicate ?object ?subjectLabel ?objectLabel ?subjectType ?objectType
        WHERE {{
            # 主查询：查找所有三元组
            ?subject ?predicate ?object .
            
            # 获取主体的标签和类型信息
            OPTIONAL {{ 
                ?subject <http://www.w3.org/2000/01/rdf-schema#label> ?subjectLabel 
            }}
            OPTIONAL {{ 
                ?subject <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> ?subjectType 
            }}
            
            # 获取客体的标签和类型信息（仅当客体是URI时）
            OPTIONAL {{ 
                ?object <http://www.w3.org/2000/01/rdf-schema#label> ?objectLabel 
                FILTER(isURI(?object))
            }}
            OPTIONAL {{ 
                ?object <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> ?objectType 
                FILTER(isURI(?object))
            }}
            
            # 过滤条件：查找与目标实体相关的三元组
            FILTER(
                # 1. 主体标签包含目标实体
                (BOUND(?subjectLabel) && (
                    CONTAINS(LCASE(STR(?subjectLabel)), LCASE("{escaped_entity_text}")) ||
                    STR(?subjectLabel) = "{escaped_entity_text}"
                )) ||
                
                # 2. 客体标签包含目标实体
                (BOUND(?objectLabel) && (
                    CONTAINS(LCASE(STR(?objectLabel)), LCASE("{escaped_entity_text}")) ||
                    STR(?objectLabel) = "{escaped_entity_text}"
                )) ||
                
                # 3. 主体URI包含目标实体
                CONTAINS(LCASE(STR(?subject)), LCASE("{escaped_entity_text}")) ||
                
                # 4. 客体URI包含目标实体（当客体是URI时）
                (isURI(?object) && CONTAINS(LCASE(STR(?object)), LCASE("{escaped_entity_text}"))) ||
                
                # 5. 客体字面量值包含目标实体（当客体是字面量时）
                (isLiteral(?object) && (
                    CONTAINS(LCASE(STR(?object)), LCASE("{escaped_entity_text}")) ||
                    STR(?object) = "{escaped_entity_text}"
                ))
            )
        }}
        ORDER BY ?subject ?predicate ?object
        LIMIT 100
        """
        
        print(f"\n--- 生成的SPARQL查询 ---")
        print(sparql_query)
        print(f"--- SPARQL查询结束 ---\n")
        
        logger.debug(f"生成的SPARQL查询:\n{sparql_query}")
        
        # 调用gstore查询接口
        print(f"正在发送请求到GStore...")
        response = _execute_gstore_query(sparql_query)
        
        print(f"GStore响应状态: {'成功' if response else '失败'}")
        
        logger.debug(f"GStore响应: {json.dumps(response, indent=2, ensure_ascii=False)}")
        
        if response and "results" in response and "bindings" in response["results"]:
            bindings = response["results"]["bindings"]
            print(f"原始查询结果数量: {len(bindings)} 条")
            logger.info(f"查询到 {len(bindings)} 条原始结果")
            
            # 打印前3条原始结果作为样例
            if bindings:
                print(f"\n--- 前3条原始结果样例 ---")
                for i, binding in enumerate(bindings[:3]):
                    print(f"结果 {i+1}: {json.dumps(binding, ensure_ascii=False, indent=2)}")
                print(f"--- 原始结果样例结束 ---\n")
            
            parsed_result = _parse_gstore_response(bindings, entity_text)
            
            print(f"解析后节点数量: {len(parsed_result['nodes'])}")
            print(f"解析后关系数量: {len(parsed_result['relations'])}")
            
            # 打印解析后的节点和关系概要
            if parsed_result['nodes']:
                print(f"\n--- 解析后的节点概要 ---")
                for i, node in enumerate(parsed_result['nodes'][:3]):
                    print(f"节点 {i+1}: ID={node.get('id', 'N/A')}, Label={node.get('label', 'N/A')}")
                if len(parsed_result['nodes']) > 3:
                    print(f"... 还有 {len(parsed_result['nodes']) - 3} 个节点")
                print(f"--- 节点概要结束 ---\n")
            
            if parsed_result['relations']:
                print(f"\n--- 解析后的关系概要 ---")
                for i, relation in enumerate(parsed_result['relations'][:3]):
                    print(f"关系 {i+1}: {relation.get('source', 'N/A')} -> {relation.get('relation', 'N/A')} -> {relation.get('target', 'N/A')}")
                if len(parsed_result['relations']) > 3:
                    print(f"... 还有 {len(parsed_result['relations']) - 3} 个关系")
                print(f"--- 关系概要结束 ---\n")
            
            logger.info(f"解析后得到 {len(parsed_result['nodes'])} 个节点, {len(parsed_result['relations'])} 个关系")
            
            print(f"=== SPARQL查询完成 ===\n")
            return parsed_result
        else:
            print(f"⚠️  GStore响应格式异常: 缺少results或bindings字段")
            print(f"响应内容: {json.dumps(response, ensure_ascii=False, indent=2) if response else 'None'}")
            logger.warning("GStore响应中没有results或bindings字段")
            print(f"=== SPARQL查询完成（无结果） ===\n")
            return {"nodes": [], "relations": []}
            
    except Exception as e:
        print(f"❌ SPARQL查询失败: {e}")
        logger.error(f"查询gstore失败: {e}", exc_info=True)
        print(f"=== SPARQL查询失败 ===\n")
        return {"nodes": [], "relations": []}

def _execute_gstore_query(sparql_query: str) -> Dict[str, Any]:
    """
    执行gstore SPARQL查询
    """
    url = f"{GSTORE_BASE_URL}/query"
    print(f"请求URL: {url}")
    logger.debug(f"请求URL: {url}")
    
    payload = {
        "operation": "query",
        "username": GSTORE_USERNAME,
        "password": GSTORE_PASSWORD,
        "db_name": GSTORE_DB_NAME,
        "sparql": sparql_query
    }
    
    print(f"数据库名称: {GSTORE_DB_NAME}")
    print(f"用户名: {GSTORE_USERNAME}")
    
    logger.debug(f"请求payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
    
    try:
        print(f"发送HTTP POST请求...")
        response = requests.post(
            url, 
            json=payload, 
            headers=_get_gstore_headers(),
            timeout=30
        )
        
        print(f"HTTP状态码: {response.status_code}")
        logger.debug(f"HTTP状态码: {response.status_code}")
        logger.debug(f"响应头: {dict(response.headers)}")
        
        if response.status_code != 200:
            print(f"❌ HTTP请求失败，状态码: {response.status_code}")
            print(f"响应内容: {response.text}")
        
        response.raise_for_status()
        
        response_json = response.json()
        print(f"✅ 成功获取JSON响应")
        
        # 简化的响应概要
        if isinstance(response_json, dict):
            if "results" in response_json:
                bindings_count = len(response_json.get("results", {}).get("bindings", []))
                print(f"响应包含 {bindings_count} 条绑定结果")
            else:
                print(f"响应字段: {list(response_json.keys())}")
        
        logger.debug(f"响应JSON: {json.dumps(response_json, indent=2, ensure_ascii=False)}")
        
        return response_json
        
    except requests.exceptions.RequestException as e:
        print(f"❌ HTTP请求异常: {e}")
        logger.error(f"HTTP请求失败: {e}")
        raise
    except json.JSONDecodeError as e:
        print(f"❌ JSON解析失败: {e}")
        print(f"原始响应: {response.text}")
        logger.error(f"JSON解析失败: {e}")
        logger.error(f"原始响应内容: {response.text}")
        raise

def _parse_gstore_response(bindings: List[Dict], entity_text: str) -> Dict[str, Any]:
    """
    解析gstore查询响应，提取节点和关系 - 增强版本
    """
    logger.debug(f"开始解析 {len(bindings)} 条绑定结果")
    
    nodes = {}
    relations = []
    
    for i, binding in enumerate(bindings):
        logger.debug(f"处理第 {i+1} 条绑定: {binding}")
        
        # 提取主体节点
        if "subject" in binding:
            subject_uri = binding["subject"]["value"]
            
            # 获取主体标签，优先使用rdfs:label，否则从URI提取
            subject_label = None
            if "subjectLabel" in binding:
                subject_label = binding["subjectLabel"]["value"]
                logger.debug(f"找到主体标签: {subject_label}")
            else:
                # 从URI提取标签
                if "#" in subject_uri:
                    subject_label = subject_uri.split("#")[-1]
                elif "/" in subject_uri:
                    subject_label = subject_uri.split("/")[-1]
                else:
                    subject_label = subject_uri
                logger.debug(f"从URI提取主体标签: {subject_label}")
            
            # 获取主体类型
            subject_type = binding.get("subjectType", {}).get("value", "")
            
            if subject_uri not in nodes:
                nodes[subject_uri] = {
                    "id": subject_uri,
                    "label": subject_label,
                    "type": subject_type,
                    "properties": {}
                }
                logger.debug(f"添加主体节点: {subject_uri} -> {subject_label}")
        
        # 提取客体节点（仅当客体是URI时）
        if "object" in binding:
            object_value = binding["object"]["value"]
            object_type_info = binding["object"].get("type", "")
            
            logger.debug(f"处理客体: {object_value}, 类型: {object_type_info}")
            
            # 只为URI类型的客体创建节点
            if object_type_info == "uri" or object_value.startswith("http"):
                # 获取客体标签
                object_label = None
                if "objectLabel" in binding:
                    object_label = binding["objectLabel"]["value"]
                    logger.debug(f"找到客体标签: {object_label}")
                else:
                    # 从URI提取标签
                    if "#" in object_value:
                        object_label = object_value.split("#")[-1]
                    elif "/" in object_value:
                        object_label = object_value.split("/")[-1]
                    else:
                        object_label = object_value
                    logger.debug(f"从URI提取客体标签: {object_label}")
                
                # 获取客体类型
                object_type = binding.get("objectType", {}).get("value", "")
                
                if object_value not in nodes:
                    nodes[object_value] = {
                        "id": object_value,
                        "label": object_label,
                        "type": object_type,
                        "properties": {}
                    }
                    logger.debug(f"添加客体节点: {object_value} -> {object_label}")
        
        # 提取关系
        if "subject" in binding and "predicate" in binding and "object" in binding:
            predicate_uri = binding["predicate"]["value"]
            object_value = binding["object"]["value"]
            object_type_info = binding["object"].get("type", "")
            
            # 提取谓词标签
            if "#" in predicate_uri:
                predicate_label = predicate_uri.split("#")[-1]
            elif "/" in predicate_uri:
                predicate_label = predicate_uri.split("/")[-1]
            else:
                predicate_label = predicate_uri
            
            # 构建关系对象
            relation = {
                "source": binding["subject"]["value"],
                "target": object_value,
                "relation": predicate_label,
                "predicate_uri": predicate_uri,
                "properties": {}
            }
            
            # 如果客体是字面量，添加额外信息
            if object_type_info == "literal" or not object_value.startswith("http"):
                relation["target_type"] = "literal"
                relation["target_value"] = object_value
            else:
                relation["target_type"] = "uri"
            
            relations.append(relation)
            logger.debug(f"添加关系: {binding['subject']['value']} -> {predicate_label} -> {object_value}")
    
    logger.info(f"解析完成: {len(nodes)} 个节点, {len(relations)} 个关系")
    
    return {
        "nodes": list(nodes.values()),
        "relations": relations
    }

def test_gstore_connection() -> bool:
    """
    测试gstore连接
    """
    logger.info("测试GStore连接...")
    
    try:
        url = f"{GSTORE_BASE_URL}/query"
        payload = {
            "operation": "query",
            "username": GSTORE_USERNAME,
            "password": GSTORE_PASSWORD,
            "db_name": GSTORE_DB_NAME,
            "sparql": "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 1"
        }
        
        logger.debug(f"连接测试URL: {url}")
        logger.debug(f"连接测试payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        
        response = requests.post(
            url, 
            json=payload, 
            headers=_get_gstore_headers(),
            timeout=10
        )
        
        logger.debug(f"连接测试响应状态: {response.status_code}")
        logger.debug(f"连接测试响应内容: {response.text}")
        
        success = response.status_code == 200
        logger.info(f"GStore连接测试结果: {'成功' if success else '失败'}")
        
        return success
        
    except Exception as e:
        logger.error(f"GStore连接测试失败: {e}", exc_info=True)
        return False