import os
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from backend.config.settings import app_config
from backend.config.logging import logger


MODEL_CONFIGS = {
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": "",
        "chat_model": "qwen-turbo-latest",
        "embedding_model": "text-embedding-v1"
    }
}

DEFAULT_LLM_TYPE = "qwen"
DEFAULT_TEMPERATURE = 0

class LLMInitializationError(Exception):
    pass

def initialize_llm(llm_type: str = DEFAULT_LLM_TYPE):
    try:
        if llm_type not in MODEL_CONFIGS:
            raise ValueError(f"不支持的LLM类型: {llm_type}. 可用类型: {list(MODEL_CONFIGS.keys())}")
        config = MODEL_CONFIGS[llm_type]
        if llm_type == "ollama":
            os.environ["OPENAI_API_KEY"] = "NA"
        llm_chat = ChatOpenAI(
            base_url=config["base_url"],
            api_key=config["api_key"],
            model=config["chat_model"],
            temperature=DEFAULT_TEMPERATURE,
            timeout=30,
            max_retries=2
        )
        llm_embedding = OpenAIEmbeddings(
            base_url=config["base_url"],
            api_key=config["api_key"],
            model=config["embedding_model"],
            deployment=config["embedding_model"]
        )
        logger.info(f"成功初始化 {llm_type} LLM")
        return llm_chat, llm_embedding
    except ValueError as ve:
        logger.error(f"LLM配置错误: {str(ve)}")
        raise LLMInitializationError(f"LLM配置错误: {str(ve)}")
    except Exception as e:
        logger.error(f"初始化LLM失败: {str(e)}")
        raise LLMInitializationError(f"初始化LLM失败: {str(e)}")

def get_llm(llm_type: str = DEFAULT_LLM_TYPE):
    try:
        return initialize_llm(llm_type)
    except LLMInitializationError as e:
        logger.warning(f"使用默认配置重试: {str(e)}")
        if llm_type != DEFAULT_LLM_TYPE:
            return initialize_llm(DEFAULT_LLM_TYPE)
        raise 