import os
from dotenv import load_dotenv

load_dotenv()

FLOWISE_BASE_URL = os.getenv("FLOWISE_BASE_URL", "http://localhost:8888")
FLOWISE_CHATFLOW_ID = os.getenv("FLOWISE_CHATFLOW_ID", "acf73857-57bc-4980-b82c-c6f5657fb8b5")
FLOWISE_API_KEY = os.getenv("FLOWISE_API_KEY", "RmiRXq1iKhakxxfEnEMjvwjy5ifwfWH3oxcb_4S3CIg")

# spring的图片识别
MERMAID_URL=os.getenv("MERMAID_URL", "http://localhost:8085/api/mermaid/replace-with-images")
# 基座模型ollama
OLLAMA_URL=os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL=os.getenv("OLLAMA_MODEL", "qwen:7b-chat")
# 对话流
FLOWISE_CHATFLOW_ID_1 = os.getenv("FLOWISE_CHATFLOW_ID_1", "acf73857-57bc-4980-b82c-c6f5657fb8b5")
FLOWISE_CHATFLOW_ID_2 = os.getenv("FLOWISE_CHATFLOW_ID_2", "acf73857-57bc-4980-b82c-c6f5657fb8b5")
FLOWISE_CHATFLOW_ID_3 = os.getenv("FLOWISE_CHATFLOW_ID_3", "acf73857-57bc-4980-b82c-c6f5657fb8b5")
FLOWISE_CHATFLOW_ID_4 = os.getenv("FLOWISE_CHATFLOW_ID_4", "acf73857-57bc-4980-b82c-c6f5657fb8b5")





# GStore配置
GSTORE_BASE_URL = os.getenv("GSTORE_BASE_URL", "http://localhost:9999") # gstore接口
GSTORE_USERNAME = os.getenv("GSTORE_USERNAME", "root")
GSTORE_PASSWORD = os.getenv("GSTORE_PASSWORD", "123456")
GSTORE_DB_NAME = os.getenv("GSTORE_DB_NAME", "celebrity_db") # 图数据库

APP_PORT = int(os.getenv("APP_PORT", "8088"))

DB_HOST = os.getenv("DB_HOST", "127.0.0.1") # mysql数据库
DB_PORT = int(os.getenv("DB_PORT", "3308"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "123456")
DB_NAME = os.getenv("DB_NAME", "modeldev") # mysql数据库的名称
DB_ECHO = os.getenv("DB_ECHO", "false").lower() == "true"

def mysql_url() -> str:
    return (
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}"
        f"@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
    )