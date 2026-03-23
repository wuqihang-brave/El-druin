import os
from functools import lru_cache
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """全局��置"""
    
    # ============ App ============
    APP_NAME: str = "El-druin Intelligence Platform"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = Field(default=False, env="DEBUG")
    
    # ============ LLM 配置 ============
    LLM_PROVIDER: Literal["groq", "openai"] = Field(
        default="groq", 
        env="LLM_PROVIDER"
    )
    GROQ_API_KEY: str = Field(default="", env="GROQ_API_KEY")
    OPENAI_API_KEY: str = Field(default="", env="OPENAI_API_KEY")
    LLM_MODEL: str = Field(default="mixtral-8x7b-32768", env="LLM_MODEL")
    LLM_TEMPERATURE: float = Field(default=0.7, env="LLM_TEMPERATURE")
    LLM_MAX_TOKENS: int = Field(default=2048, env="LLM_MAX_TOKENS")
    
    # ============ 知识图数据库 ============
    KG_DB_TYPE: Literal["kuzu", "neo4j"] = Field(
        default="kuzu",
        env="KG_DB_TYPE"
    )
    KUZU_DB_PATH: str = Field(default="./data/kuzu_db", env="KUZU_DB_PATH")
    
    # ============ 缓存 ============
    CACHE_TYPE: Literal["memory", "redis"] = Field(
        default="memory",
        env="CACHE_TYPE"
    )
    REDIS_URL: str = Field(default="redis://localhost:6379", env="REDIS_URL")
    CACHE_TTL: int = Field(default=3600, env="CACHE_TTL")
    
    # ============ 新闻源 ============
    NEWS_SOURCES: str = Field(default="xinhua,bbc,reuters", env="NEWS_SOURCES")
    NEWS_FETCH_INTERVAL: int = Field(default=300, env="NEWS_FETCH_INTERVAL")
    NEWS_MAX_ITEMS: int = Field(default=50, env="NEWS_MAX_ITEMS")
    
    # ============ Entity Extraction ============
    ENTITY_TYPES: str = Field(
        default="PERSON,ORGANIZATION,LOCATION,EVENT,TIME,MONEY,PERCENT",
        env="ENTITY_TYPES"
    )
    RELATION_TYPES: str = Field(
        default="WORKS_FOR,LOCATED_IN,PARTICIPATES_IN,OWNS,MANAGES,MARRIED_TO,BORN_IN",
        env="RELATION_TYPES"
    )
    CONFIDENCE_THRESHOLD: float = Field(default=0.6, env="CONFIDENCE_THRESHOLD")
    
    # ============ 多代理 ============
    NUM_AGENTS: int = Field(default=3, env="NUM_AGENTS")
    AGENT_TIMEOUT: int = Field(default=30, env="AGENT_TIMEOUT")
    
    # ============ 日志 ============
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LOG_FILE: str = Field(default="./logs/el-druin.log", env="LOG_FILE")
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow"


@lru_cache()
def get_settings() -> Settings:
    """单例模式获取配置"""
    return Settings()


settings = get_settings()
