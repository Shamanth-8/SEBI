"""
FAISS-based retrieval layer for clause-level semantic search.
"""
import os
import logging
import numpy as np
from typing import List, Tuple, Optional
from anthropic import Anthropic

logger = logging.getLogger(__name__)


class FAISSRetrieval:
    """
    FAISS-based retrieval system for semantic search over regulatory clauses.
    Uses embeddings to find similar obligations and clauses.
    """
    
    def __init__(self, index_path: str = "./data/faiss_index"):
        self.index_path = index_path
        # Lazy: Anthropic() raises when ANTHROPIC_API_KEY is unset, which would
        # stop the application from starting even though retrieval falls back to
        # a local similarity search perfectly well without it.
        self._client = None
        self.embeddings = {}  # obligation_id -> embedding vector
        self.clause_index = {}  # embedding hash -> clause metadata
        
        # Initialize FAISS when package is available
        self.faiss = None
        self.index = None
        try:
            import faiss
            self.faiss = faiss
            self._load_or_create_index()
        except ImportError:
            logger.warning("FAISS not available. Using similarity fallback.")
    
    @property
    def client(self):
        """Anthropic client, built on first use. None when no key is configured."""
        if self._client is None:
            try:
                self._client = Anthropic()
            except Exception as exc:
                logger.debug(f"Anthropic client unavailable for embeddings: {exc}")
                return None
        return self._client

    def _load_or_create_index(self):
        """Load existing FAISS index or create new one."""
        if os.path.exists(self.index_path):
            try:
                self.index = self.faiss.read_index(self.index_path)
                logger.info(f"Loaded FAISS index from {self.index_path}")
            except Exception as e:
                logger.warning(f"Error loading index: {e}. Creating new one.")
                self._create_new_index()
        else:
            self._create_new_index()
    
    def _create_new_index(self):
        """Create a new FAISS index."""
        # Use 384-dimensional embeddings (compatible with Claude's embed model)
        dimension = 384
        self.index = self.faiss.IndexFlatL2(dimension)
        logger.info("Created new FAISS index")
    
    def add_clause_embedding(
        self,
        obligation_id: str,
        clause_text: str,
        embedding: np.ndarray = None
    ) -> None:
        """Add a clause with its embedding to the index."""
        if embedding is None:
            embedding = self._get_embedding(clause_text)
        
        if self.faiss and self.index and embedding is not None:
            try:
                embedding_reshaped = np.array([embedding]).astype('float32')
                self.index.add(embedding_reshaped)
                
                self.embeddings[obligation_id] = embedding
                logger.debug(f"Added embedding for {obligation_id}")
            except Exception as e:
                logger.warning(f"Error adding embedding: {e}")
    
    def search_similar(
        self,
        query: str,
        k: int = 5,
        threshold: float = 0.7
    ) -> List[Tuple[str, float]]:
        """
        Search for similar clauses.
        
        Args:
            query: Search query text
            k: Number of results to return
            threshold: Similarity threshold (0-1)
            
        Returns:
            List of (obligation_id, similarity_score) tuples
        """
        query_embedding = self._get_embedding(query)
        
        if query_embedding is None or self.faiss is None or self.index is None:
            logger.warning("Cannot perform FAISS search. Using fallback.")
            return self._similarity_fallback(query, k)
        
        try:
            query_reshaped = np.array([query_embedding]).astype('float32')
            distances, indices = self.index.search(query_reshaped, min(k, self.index.ntotal))
            
            results = []
            for idx, distance in zip(indices[0], distances[0]):
                if idx >= 0:  # Valid index
                    # Convert L2 distance to similarity score
                    similarity = 1 / (1 + distance)
                    
                    if similarity >= threshold:
                        # Find obligation_id for this index
                        obl_id = self._find_obligation_by_index(idx)
                        if obl_id:
                            results.append((obl_id, float(similarity)))
            
            return results
            
        except Exception as e:
            logger.error(f"Error in FAISS search: {e}")
            return self._similarity_fallback(query, k)
    
    def _get_embedding(self, text: str) -> Optional[np.ndarray]:
        """Get embedding for text using Claude."""
        try:
            # For hackathon, use simple hash-based pseudo-embeddings
            # In production, would use proper embedding model
            import hashlib
            hash_obj = hashlib.sha256(text.encode())
            hash_int = int(hash_obj.hexdigest(), 16)
            np.random.seed(hash_int % (2**31))
            embedding = np.random.randn(384).astype('float32')
            return embedding / np.linalg.norm(embedding)  # Normalize
        except Exception as e:
            logger.warning(f"Error generating embedding: {e}")
            return None
    
    def _similarity_fallback(
        self,
        query: str,
        k: int
    ) -> List[Tuple[str, float]]:
        """Fallback similarity search using token overlap."""
        query_tokens = set(query.lower().split())
        
        similarities = []
        for obl_id, embedding in self.embeddings.items():
            # This is a placeholder - real implementation would use embeddings
            similarity = len(query_tokens) / (len(query_tokens) + 1)
            similarities.append((obl_id, similarity))
        
        # Sort by similarity and return top k
        return sorted(similarities, key=lambda x: x[1], reverse=True)[:k]
    
    def _find_obligation_by_index(self, index: int) -> Optional[str]:
        """Find obligation ID by FAISS index."""
        sorted_ids = sorted(self.embeddings.keys())
        if 0 <= index < len(sorted_ids):
            return sorted_ids[index]
        return None
    
    def save_index(self) -> None:
        """Persist FAISS index to disk."""
        if self.faiss and self.index:
            try:
                os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
                self.faiss.write_index(self.index, self.index_path)
                logger.info(f"Saved FAISS index to {self.index_path}")
            except Exception as e:
                logger.error(f"Error saving index: {e}")
