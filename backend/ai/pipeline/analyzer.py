"""
Core AI Analysis Pipeline
Runs: sentiment → emotion → sarcasm → LSTM risk → feed score
"""

import numpy as np
import logging
from schemas.schemas import PipelineResult
from ai.pipeline.loader import get_model

logger = logging.getLogger("mindgram.pipeline")

# Label mappings
SENTIMENT_MAP = {
    "LABEL_0": ("negative", -1.0),
    "LABEL_1": ("neutral",   0.0),
    "LABEL_2": ("positive",  1.0),
}

EMOTION_LABELS = {
    "anger": "anger",
    "disgust": "disgust",
    "fear": "fear",
    "joy": "joy",
    "neutral": "neutral",
    "sadness": "sadness",
    "surprise": "surprise",
}

# Negative emotions (used in risk scoring)
NEGATIVE_EMOTIONS = {"anger", "disgust", "fear", "sadness"}


def run_sentiment(text: str) -> tuple[str, float]:
    """Returns (label, normalized_score ∈ [-1, 1])."""
    model = get_model("sentiment")
    result = model(text)[0]
    label_raw = result["label"]
    conf = result["score"]
    label, direction = SENTIMENT_MAP.get(label_raw, ("neutral", 0.0))
    score = direction * conf
    return label, round(score, 4)


def run_emotion(text: str) -> tuple[str, float]:
    """Returns (emotion_label, confidence ∈ [0, 1])."""
    model = get_model("emotion")
    result = model(text)[0]
    label = result["label"].lower()
    label = EMOTION_LABELS.get(label, "neutral")
    return label, round(result["score"], 4)


def run_sarcasm(text: str) -> tuple[bool, float]:
    """Returns (is_sarcastic, confidence ∈ [0, 1])."""
    model = get_model("sarcasm")
    result = model(text)[0]
    is_irony = result["label"].lower() == "irony"
    return is_irony, round(result["score"], 4)


def compute_instant_risk(
    sentiment_score: float,
    emotion: str,
    emotion_score: float,
    is_sarcastic: bool,
) -> float:
    """
    Heuristic instant risk score before LSTM.
    risk ∈ [0, 1]
    """
    # Base: negative sentiment pushes risk up
    base = max(0.0, -sentiment_score)  # 0–1

    # Emotion modifier
    emotion_weight = 0.0
    if emotion in NEGATIVE_EMOTIONS:
        emotion_weight = emotion_score * 0.4

    # Sarcasm can mask true negativity — small boost
    sarcasm_boost = 0.1 if is_sarcastic and sentiment_score >= 0 else 0.0

    risk = min(1.0, base * 0.5 + emotion_weight + sarcasm_boost)
    return round(risk, 4)


def compute_feed_score(
    sentiment_score: float,
    risk_score: float,
    likes_count: int = 0,
    comments_count: int = 0,
) -> float:
    """
    Adaptive feed score.
    High positive sentiment + engagement = higher score.
    High risk = depressed score.
    feed_score ∈ [0, 1]
    """
    positivity = (sentiment_score + 1.0) / 2.0   # map [-1,1] → [0,1]
    engagement = min(1.0, (likes_count + comments_count * 2) / 100.0)
    penalty = risk_score * 0.6
    score = positivity * 0.5 + engagement * 0.3 - penalty
    return round(max(0.0, min(1.0, score + 0.2)), 4)  # +0.2 baseline


def run_lstm_risk(user_risk_history: list[float]) -> float:
    """
    Use Keras LSTM to predict updated risk from temporal sequence.
    user_risk_history: list of recent risk scores (up to 20)
    Returns updated risk ∈ [0, 1]
    """
    if not user_risk_history:
        return 0.0
    lstm = get_model("lstm")
    seq = user_risk_history[-20:]  # last 20 observations
    # Pad to length 20
    padded = [0.0] * (20 - len(seq)) + seq
    arr = np.array(padded, dtype=np.float32).reshape(1, 20, 1)
    prediction = lstm.predict(arr, verbose=0)[0][0]
    return round(float(np.clip(prediction, 0.0, 1.0)), 4)


def analyze_text(
    text: str,
    user_risk_history: list[float] | None = None,
    likes_count: int = 0,
    comments_count: int = 0,
) -> PipelineResult:
    """
    Full pipeline: text → PipelineResult
    """
    sentiment, sentiment_score = run_sentiment(text)
    emotion, emotion_score     = run_emotion(text)
    is_sarcastic, sarcasm_score = run_sarcasm(text)

    instant_risk = compute_instant_risk(sentiment_score, emotion, emotion_score, is_sarcastic)

    # LSTM temporal refinement
    history = (user_risk_history or []) + [instant_risk]
    lstm_risk = run_lstm_risk(history)

    # Blend instant + LSTM
    risk_score = round(instant_risk * 0.3 + lstm_risk * 0.7, 4) if lstm_risk > 0 else instant_risk

    feed_score = compute_feed_score(sentiment_score, risk_score, likes_count, comments_count)

    logger.debug(
        f"Pipeline → sentiment={sentiment}({sentiment_score}), "
        f"emotion={emotion}({emotion_score}), sarcasm={is_sarcastic}, "
        f"risk={risk_score}, feed={feed_score}"
    )

    return PipelineResult(
        sentiment=sentiment,
        sentiment_score=sentiment_score,
        emotion=emotion,
        emotion_score=emotion_score,
        sarcasm=is_sarcastic,
        sarcasm_score=sarcasm_score,
        risk_score=risk_score,
        feed_score=feed_score,
    )
