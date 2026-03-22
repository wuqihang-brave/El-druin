"""Configuration management using pydantic-settings."""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://eldruin:eldruin@localhost:5432/eldruin",
        description="PostgreSQL connection URL",
    )

    # Neo4j
    NEO4J_URL: str = Field(default="bolt://localhost:7687")
    NEO4J_USER: str = Field(default="neo4j")
    NEO4J_PASSWORD: str = Field(default="password")

    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # Pinecone
    PINECONE_API_KEY: Optional[str] = Field(default=None)
    PINECONE_ENVIRONMENT: Optional[str] = Field(default=None)
    PINECONE_INDEX_NAME: str = Field(default="eldruin-events")

    # OpenAI
    OPENAI_API_KEY: Optional[str] = Field(default=None)
    OPENAI_MODEL: str = Field(default="gpt-4-turbo-preview")

    # JWT
    JWT_SECRET_KEY: str = Field(default="change-me-in-production-use-256-bit-key")
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60)

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = Field(default="localhost:9092")
    KAFKA_TOPIC_EVENTS: str = Field(default="eldruin.events")
    KAFKA_TOPIC_PREDICTIONS: str = Field(default="eldruin.predictions")
    KAFKA_CONSUMER_GROUP: str = Field(default="eldruin-consumer-group")

    # App
    ENVIRONMENT: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")
    CORS_ORIGINS: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"]
    )

    # Embeddings
    EMBEDDING_MODEL: str = Field(default="all-MiniLM-L6-v2")
    EMBEDDING_DIMENSION: int = Field(default=384)

    # Rate limiting
    RATE_LIMIT_REQUESTS: int = Field(default=100)
    RATE_LIMIT_WINDOW_SECONDS: int = Field(default=60)


settings = Settings()
