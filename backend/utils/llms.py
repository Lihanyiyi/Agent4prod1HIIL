from langchain_openai import ChatOpenAI
from .config import Config

def get_llm():
    """
    获取LLM实例
    
    Returns:
        ChatOpenAI: LLM实例
    """
    try:
        # 根据配置创建LLM实例
        if Config.LLM_TYPE.lower() == "qwen":
            # 使用通义千问模型
            llm = ChatOpenAI(
                model="qwen-turbo",
                api_key=Config.OPENAI_API_KEY,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                temperature=0.7,
                max_tokens=4000
            )
        else:
            # 默认使用OpenAI模型
            llm = ChatOpenAI(
                model="gpt-3.5-turbo",
                api_key=Config.OPENAI_API_KEY,
                temperature=0.7,
                max_tokens=4000
            )
        
        return llm
        
    except Exception as e:
        raise Exception(f"创建LLM实例失败: {str(e)}") 