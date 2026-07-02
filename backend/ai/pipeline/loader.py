"""
AI Model Loader — singleton pattern so models load once at startup.

Models used:
  - cardiffnlp/twitter-roberta-base-sentiment  → sentiment
  - j-hartmann/emotion-english-distilroberta-base → emotion
  - cardiffnlp/twitter-roberta-base-irony       → sarcasm/irony
  - all-MiniLM-L6-v2 (sentence-transformers)   → RAG embeddings
  - Keras LSTM (built locally)                  → temporal risk scoring
"""

import logging
from transformers import pipeline as hf_pipeline
from sentence_transformers import SentenceTransformer

logger = logging.getLogger("mindgram.loader")

# Global model handles
_models = {}


def preload_models():
    """Load all HuggingFace + sentence-transformer models into memory."""
    logger.info("Loading sentiment model (RoBERTa)...")
    _models["sentiment"] = hf_pipeline(
        "text-classification",
        model="cardiffnlp/twitter-roberta-base-sentiment-latest",
        top_k=1,
        truncation=True,
        max_length=512,
    )

    logger.info("Loading emotion model (distilRoBERTa)...")
    _models["emotion"] = hf_pipeline(
        "text-classification",
        model="j-hartmann/emotion-english-distilroberta-base",
        top_k=1,
        truncation=True,
        max_length=512,
    )

    logger.info("Loading sarcasm/irony model (RoBERTa)...")
    _models["sarcasm"] = hf_pipeline(
        "text-classification",
        model="cardiffnlp/twitter-roberta-base-irony",
        top_k=1,
        truncation=True,
        max_length=512,
    )

    logger.info("Loading sentence-transformer (MiniLM)...")
    _models["embedder"] = SentenceTransformer("all-MiniLM-L6-v2")

    logger.info("Building / loading Keras LSTM risk model...")
    from ai.pipeline.lstm_risk import build_or_load_lstm
    _models["lstm"] = build_or_load_lstm()

    logger.info("✅ All models loaded.")


def get_model(name: str):
    if name not in _models:
        raise RuntimeError(f"Model '{name}' not loaded. Call preload_models() first.")
    return _models[name]
