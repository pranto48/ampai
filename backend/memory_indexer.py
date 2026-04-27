import os
from datetime import datetime, timezone
from langchain_postgres import PGVector
from langchain_core.documents import Document
from database import get_config, DATABASE_URL

def get_embedding_model(model_type: str = "ollama"):
    if model_type == "openai":
        from langchain_openai import OpenAIEmbeddings
        key = get_config("openai_api_key") or os.getenv("OPENAI_API_KEY")
        if not key:
            raise ValueError("OpenAI API key missing for embeddings")
        return OpenAIEmbeddings(api_key=key)
    elif model_type == "gemini":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        key = get_config("gemini_api_key") or os.getenv("GOOGLE_API_KEY")
        if not key:
            raise ValueError("Google API key missing for embeddings")
        return GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=key)
    else:
        # Default to Ollama nomic-embed-text for local indexing
        from langchain_community.embeddings import OllamaEmbeddings
        base_url = get_config("ollama_base_url") or os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
        return OllamaEmbeddings(model="nomic-embed-text", base_url=base_url)

class MemoryIndexer:
    def __init__(self, model_type: str = "ollama"):
        try:
            self.embedding_model = get_embedding_model(model_type)
            self.vectorstore = PGVector(
                embeddings=self.embedding_model,
                collection_name="chat_memory",
                connection=DATABASE_URL,
                use_jsonb=True,
            )
            self.enabled = True
        except Exception as e:
            print(f"Memory Indexer Disabled (PGVector initialization failed): {e}")
            self.enabled = False

    def add_fact(self, fact: str):
        if not self.enabled: return
        try:
            doc = Document(
                page_content=fact,
                metadata={
                    "type": "distilled_fact",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            self.vectorstore.add_documents([doc])
        except Exception as e:
            print(f"PGVector Add Error: {e}")

    def search_facts(self, query: str, k: int = 5, recency_bias: float = 0.0, category_filter: str = None):
        if not self.enabled: return []
        try:
            search_filter = {"type": "distilled_fact"}
            if category_filter:
                search_filter["category"] = category_filter
            results = self.vectorstore.similarity_search(
                query,
                k=k,
                filter=search_filter
            )
            if recency_bias > 0:
                now = datetime.now(timezone.utc)

                def _sort_key(doc):
                    created_at = doc.metadata.get("created_at") if getattr(doc, "metadata", None) else None
                    if not created_at:
                        return 0.0
                    try:
                        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                        age_days = max(0.0, (now - dt).total_seconds() / 86400.0)
                        return 1.0 / (1.0 + age_days)
                    except Exception:
                        return 0.0

                top_n = max(1, int(k))
                recency_sorted = sorted(results, key=_sort_key, reverse=True)
                keep_recent = int(round(top_n * recency_bias))
                keep_recent = max(0, min(top_n, keep_recent))
                blended = recency_sorted[:keep_recent] + [doc for doc in results if doc not in recency_sorted[:keep_recent]]
                results = blended[:top_n]

            return [doc.page_content for doc in results]
        except Exception as e:
            print(f"PGVector Search Error: {e}")
            return []
