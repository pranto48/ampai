import os
import json
import gzip
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from database import engine, get_config
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

# Memory archiving configuration
ARCHIVE_THRESHOLD_DAYS = int(os.getenv("MEMORY_ARCHIVE_THRESHOLD_DAYS", "90"))
COMPRESSION_ENABLED = os.getenv("MEMORY_COMPRESSION_ENABLED", "true").lower() == "true"
IMPORTANCE_SCORING_ENABLED = os.getenv("MEMORY_IMPORTANCE_SCORING_ENABLED", "true").lower() == "true"

class MemoryPersistenceManager:
    """
    Manages long-term memory persistence strategies including archiving,
    compression, and importance scoring.
    """
    
    def __init__(self):
        self._lock = threading.Lock()
        self._archive_lock = threading.Lock()
        
    def initialize(self):
        """
        Initialize the memory persistence manager.
        """
        # Currently no specific initialization needed
        # This method exists to satisfy the API contract
        logger.info("Memory persistence manager initialized")
        pass
        
    def calculate_importance_score(self, memory_text: str, access_count: int, last_accessed: Optional[datetime]) -> float:
        """
        Calculate an importance score for a memory based on multiple factors.
        
        Args:
            memory_text: The text content of the memory
            access_count: Number of times this memory has been accessed
            last_accessed: When this memory was last accessed
            
        Returns:
            Importance score between 0.0 and 1.0
        """
        if not IMPORTANCE_SCORING_ENABLED:
            return 1.0
            
        # Base score from text analysis
        base_score = self._analyze_text_importance(memory_text)
        
        # Recency factor (more recent = more important)
        recency_factor = 1.0
        if last_accessed:
            days_since_access = (datetime.now() - last_accessed).days
            # More recent access increases importance
            recency_factor = max(0.1, 1.0 - (days_since_access / 365.0))
        
        # Frequency factor (more accessed = more important)
        frequency_factor = min(1.0, access_count / 10.0)
        
        # Combine factors with weights
        final_score = (
            base_score * 0.5 +  # 50% text importance
            recency_factor * 0.3 +  # 30% recency
            frequency_factor * 0.2  # 20% frequency
        )
        
        return min(1.0, max(0.0, final_score))
    
    def _analyze_text_importance(self, text: str) -> float:
        """
        Analyze text content to determine inherent importance.
        
        Args:
            text: The text to analyze
            
        Returns:
            Importance score between 0.0 and 1.0
        """
        if not text:
            return 0.0
            
        # Length factor (longer memories might be more important)
        length_score = min(1.0, len(text) / 500.0)
        
        # Keyword importance
        important_keywords = [
            "important", "crucial", "essential", "remember", "always", "never",
            "password", "credential", "account", "project", "deadline", "meeting"
        ]
        keyword_score = sum(1 for keyword in important_keywords if keyword.lower() in text.lower()) / len(important_keywords)
        
        # Named entity detection (simplified)
        # In a real implementation, you might use NLP libraries like spaCy
        entity_indicators = ["@", ".com", "http", "202", "192", "10.", "172."]
        entity_score = min(1.0, sum(1 for indicator in entity_indicators if indicator in text) / 5.0)
        
        # Combine factors
        return min(1.0, (length_score + keyword_score + entity_score) / 3.0)
    
    def archive_old_memories(self) -> Dict[str, int]:
        """
        Archive memories that haven't been accessed in a long time.
        
        Returns:
            Dictionary with statistics about the archiving process
        """
        if not engine:
            return {"archived": 0, "failed": 0}
            
        with self._archive_lock:
            try:
                # Find memories older than threshold
                threshold_date = datetime.now() - timedelta(days=ARCHIVE_THRESHOLD_DAYS)
                
                with engine.connect() as conn:
                    # Mark old memories as archived
                    result = conn.execute(
                        text("""
                            UPDATE memory_candidates 
                            SET archived = TRUE, archived_at = NOW()
                            WHERE created_at < :threshold 
                            AND archived = FALSE
                            AND status = 'approved'
                        """),
                        {"threshold": threshold_date}
                    )
                    archived_count = result.rowcount
                    
                    # Also archive old summary nodes
                    summary_result = conn.execute(
                        text("""
                            UPDATE memory_summary_nodes 
                            SET archived = TRUE, archived_at = NOW()
                            WHERE created_at < :threshold 
                            AND archived = FALSE
                        """),
                        {"threshold": threshold_date}
                    )
                    summary_archived_count = summary_result.rowcount
                    
                    conn.commit()
                    
                logger.info(f"Archived {archived_count} memory candidates and {summary_archived_count} summary nodes")
                return {
                    "archived": archived_count,
                    "summary_archived": summary_archived_count,
                    "failed": 0
                }
                
            except Exception as e:
                logger.error(f"Error archiving memories: {e}")
                return {"archived": 0, "summary_archived": 0, "failed": 1}
    
    def compress_memory_content(self, memory_id: int, content: str) -> Optional[bytes]:
        """
        Compress memory content for storage efficiency.
        
        Args:
            memory_id: ID of the memory
            content: Content to compress
            
        Returns:
            Compressed content as bytes, or None if compression failed
        """
        if not COMPRESSION_ENABLED:
            return None
            
        try:
            # Convert string to bytes
            content_bytes = content.encode('utf-8')
            
            # Compress with gzip
            compressed = gzip.compress(content_bytes)
            
            # Only store if compression actually saves space
            if len(compressed) < len(content_bytes):
                return compressed
            else:
                return None  # Not worth compressing
        except Exception as e:
            logger.error(f"Error compressing memory {memory_id}: {e}")
            return None
    
    def decompress_memory_content(self, compressed_data: bytes) -> Optional[str]:
        """
        Decompress memory content.
        
        Args:
            compressed_data: Compressed data as bytes
            
        Returns:
            Decompressed content as string, or None if decompression failed
        """
        if not compressed_data:
            return None
            
        try:
            decompressed_bytes = gzip.decompress(compressed_data)
            return decompressed_bytes.decode('utf-8')
        except Exception as e:
            logger.error(f"Error decompressing memory: {e}")
            return None
    
    def get_memory_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about memory persistence.
        
        Returns:
            Dictionary with memory statistics
        """
        if not engine:
            return {}
            
        try:
            with engine.connect() as conn:
                # Count total memories
                total_result = conn.execute(text("SELECT COUNT(*) FROM memory_candidates WHERE status = 'approved'"))
                total_count = total_result.scalar() or 0
                
                # Count archived memories
                archived_result = conn.execute(text("SELECT COUNT(*) FROM memory_candidates WHERE archived = TRUE AND status = 'approved'"))
                archived_count = archived_result.scalar() or 0
                
                # Count compressed memories
                compressed_result = conn.execute(text("SELECT COUNT(*) FROM memory_candidates WHERE compressed_data IS NOT NULL AND status = 'approved'"))
                compressed_count = compressed_result.scalar() or 0
                
                # Average importance score
                avg_importance_result = conn.execute(text("SELECT AVG(importance_score) FROM memory_candidates WHERE status = 'approved'"))
                avg_importance = avg_importance_result.scalar() or 0.0
                
                return {
                    "total_memories": total_count,
                    "archived_memories": archived_count,
                    "compressed_memories": compressed_count,
                    "active_memories": total_count - archived_count,
                    "compression_ratio": round(compressed_count / max(1, total_count), 4),
                    "average_importance_score": round(float(avg_importance), 4)
                }
        except Exception as e:
            logger.error(f"Error getting memory statistics: {e}")
            return {}

    def capture_memory_candidate(
        self,
        username: str,
        session_id: str,
        message_content: str,
        response_content: str,
        require_approval: bool = False,
    ) -> None:
        """
        Capture a memory candidate from a chat exchange.
        This is a lightweight hook; actual saving is handled by the
        [SAVE_MEMORY:] tag pipeline in agent.py.
        """
        try:
            if not engine or not message_content:
                return
            # Only persist if the exchange looks meaningful (heuristic)
            combined = f"{message_content} {response_content}"
            if len(combined.strip()) < 20:
                return
            score = self._analyze_text_importance(combined)
            if score < 0.15:
                return  # Not worth capturing
            status = "pending" if require_approval else "approved"
            with engine.begin() as conn:
                conn.execute(
                    text("""
                        INSERT INTO memory_candidates
                            (username, session_id, candidate_text, status, importance_score, created_at)
                        VALUES
                            (:username, :session_id, :text, :status, :score, NOW())
                        ON CONFLICT DO NOTHING
                    """),
                    {
                        "username": username or "system",
                        "session_id": session_id or "",
                        "text": (message_content or "")[:1000],
                        "status": status,
                        "score": round(score, 4),
                    },
                )
        except Exception as e:
            logger.debug(f"capture_memory_candidate skipped: {e}")

    def score_memory_candidate(
        self,
        username: str,
        session_id: str,
        message_content: str,
        response_content: str,
    ) -> None:
        """
        Update importance scores for recent memory candidates in this session.
        """
        try:
            if not engine:
                return
            combined = f"{message_content} {response_content}"
            score = self._analyze_text_importance(combined)
            with engine.begin() as conn:
                conn.execute(
                    text("""
                        UPDATE memory_candidates
                        SET importance_score = :score
                        WHERE session_id = :session_id
                          AND username = :username
                          AND importance_score IS NULL
                    """),
                    {"score": round(score, 4), "session_id": session_id or "", "username": username or "system"},
                )
        except Exception as e:
            logger.debug(f"score_memory_candidate skipped: {e}")


# Global instance
memory_persistence_manager = MemoryPersistenceManager()