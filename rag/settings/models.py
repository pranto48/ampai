# rag/settings/models.py
"""SQLAlchemy models for Settings persistence.

We keep a lightweight schema:
- ApiKey: stores API keys for external services.
- LocalModelEndpoint: stores URLs for local LLM servers (e.g., Ollama).
- Integration: generic JSON config for things like Telegram.

All tables are created at runtime if missing (see database.py migration).
"""

from sqlalchemy import Column, Integer, String, Boolean, JSON, UniqueConstraint
from .database import Base

class ApiKey(Base):
    __tablename__ = "api_keys"
    id = Column(Integer, primary_key=True, autoincrement=True)
    service = Column(String, nullable=False)  # e.g., "openai", "anthropic", "gemini"
    key = Column(String, nullable=False)
    active = Column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("service", name="uq_api_key_service"),)

class LocalModelEndpoint(Base):
    __tablename__ = "local_model_endpoints"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)  # friendly name, e.g., "ollama_meta"
    url = Column(String, nullable=False)   # e.g., "http://localhost:11434/api/generate"
    active = Column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("name", name="uq_local_endpoint_name"),)

class Integration(Base):
    __tablename__ = "integrations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String, nullable=False)  # "telegram", "automation"
    config = Column(JSON, nullable=False, default={})
    active = Column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("type", name="uq_integration_type"),)

# Export for easy imports
__all__ = ["ApiKey", "LocalModelEndpoint", "Integration"]
