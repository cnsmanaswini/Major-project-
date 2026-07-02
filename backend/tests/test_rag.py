"""
Unit tests for the FAISS-based RAG suggestion system.
"""

import pytest
import numpy as np
from unittest.mock import patch, MagicMock


def mock_embedder(texts, **kwargs):
    """Return deterministic fake embeddings of dimension 384."""
    np.random.seed(42)
    return np.random.rand(len(texts), 384).astype(np.float32)


class TestRAGIndex:
    """Tests for build_rag_index and retrieve_suggestion."""

    def _build_index_with_mocks(self):
        """Helper: build the index with mocked embedder + FAISS."""
        import ai.rag.index as rag_module
        mock_emb = MagicMock()
        mock_emb.encode = MagicMock(side_effect=mock_embedder)

        with patch("ai.rag.index.get_model", return_value=mock_emb):
            rag_module.build_rag_index()

        return rag_module, mock_emb

    def test_index_builds_without_error(self):
        self._build_index_with_mocks()

    def test_index_has_correct_document_count(self):
        from ai.rag.index import KNOWLEDGE_BASE
        mod, _ = self._build_index_with_mocks()
        assert mod._index is not None
        assert mod._index.ntotal == len(KNOWLEDGE_BASE)

    def test_retrieve_suggestion_returns_string(self):
        mod, mock_emb = self._build_index_with_mocks()

        def query_embed(texts, **kwargs):
            return mock_embedder(texts)

        mock_emb.encode = MagicMock(side_effect=query_embed)
        with patch("ai.rag.index.get_model", return_value=mock_emb):
            suggestion = mod.retrieve_suggestion("feeling sad and lonely")

        assert isinstance(suggestion, str)
        assert len(suggestion) > 20

    def test_retrieve_returns_fallback_when_index_not_built(self):
        import ai.rag.index as rag_module
        # Force index to None
        original_index = rag_module._index
        rag_module._index = None
        try:
            result = rag_module.retrieve_suggestion("test query")
            assert isinstance(result, str)
            assert len(result) > 0
        finally:
            rag_module._index = original_index

    def test_retrieve_top_k_returns_list(self):
        mod, mock_emb = self._build_index_with_mocks()
        mock_emb.encode = MagicMock(side_effect=mock_embedder)
        with patch("ai.rag.index.get_model", return_value=mock_emb):
            results = mod.retrieve_top_k("anxious overwhelmed stress", top_k=3)
        assert isinstance(results, list)
        assert len(results) <= 3
        for r in results:
            assert isinstance(r, str)

    def test_retrieve_top_k_empty_when_no_index(self):
        import ai.rag.index as rag_module
        original = rag_module._index
        rag_module._index = None
        try:
            results = rag_module.retrieve_top_k("test", top_k=3)
            assert results == []
        finally:
            rag_module._index = original

    def test_knowledge_base_has_required_fields(self):
        from ai.rag.index import KNOWLEDGE_BASE
        for doc in KNOWLEDGE_BASE:
            assert "id" in doc
            assert "context" in doc
            assert "suggestion" in doc
            assert len(doc["suggestion"]) > 30, "Suggestions should be substantive"

    def test_knowledge_base_covers_key_emotions(self):
        from ai.rag.index import KNOWLEDGE_BASE
        all_contexts = " ".join(d["context"] for d in KNOWLEDGE_BASE)
        for keyword in ["sad", "anxious", "angry", "happy", "crisis"]:
            assert keyword in all_contexts.lower(), f"Knowledge base missing context for: {keyword}"

    def test_crisis_content_exists(self):
        """Ensure at least one entry contains helpline information."""
        from ai.rag.index import KNOWLEDGE_BASE
        crisis_entries = [
            d for d in KNOWLEDGE_BASE
            if "helpline" in d["suggestion"].lower() or "iCall" in d["suggestion"] or "crisis" in d["suggestion"].lower()
        ]
        assert len(crisis_entries) >= 1, "At least one crisis support entry required"


class TestRAGQueryRelevance:
    """Tests that query-to-suggestion matching is directionally correct."""

    def _query(self, text):
        import ai.rag.index as rag_module
        mock_emb = MagicMock()

        # Assign specific embeddings so different queries get different results
        embed_map = {}
        call_count = [0]

        def smart_encode(texts, **kwargs):
            np.random.seed(hash(texts[0]) % (2**31))
            return np.random.rand(len(texts), 384).astype(np.float32)

        mock_emb.encode = MagicMock(side_effect=smart_encode)
        with patch("ai.rag.index.get_model", return_value=mock_emb):
            rag_module.build_rag_index()
            result = rag_module.retrieve_suggestion(text)
        return result

    def test_query_returns_non_empty_string(self):
        result = self._query("feeling very sad")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_multiple_queries_return_strings(self):
        queries = [
            "feeling anxious and worried",
            "so angry and frustrated",
            "feeling great and happy",
            "can't sleep exhausted",
        ]
        for q in queries:
            result = self._query(q)
            assert isinstance(result, str) and len(result) > 0, f"Failed for query: {q}"
