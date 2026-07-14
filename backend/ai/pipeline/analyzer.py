"""
Core AI Analysis Pipeline
Runs: sentiment → emotion → sarcasm → numbness/dissociation → LSTM risk → feed score
"""

import numpy as np
import logging
from schemas.schemas import PipelineResult
from ai.pipeline.loader import get_model
from ai.pipeline.numbness_detector import detect_numbness_signal
from ai.pipeline.risk_detector import detect_depression_suicide_risk, RiskTier

logger = logging.getLogger("mindgram.pipeline")

# Label mappings
# NOTE: cardiffnlp/twitter-roberta-base-sentiment-latest returns
# "negative" / "neutral" / "positive" directly (not LABEL_0/1/2 —
# that scheme belongs to the older non-"latest" checkpoint).
SENTIMENT_MAP = {
    "negative": ("negative", -1.0),
    "neutral":  ("neutral",   0.0),
    "positive": ("positive",  1.0),
    # Kept for safety in case a different checkpoint is swapped in later.
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

# Sarcasm confidence needed before we distrust the sentiment model's read.
# Only applies when sarcasm is detected AND sentiment came back positive —
# that's the specific case where a wrong sentiment reading would otherwise
# suppress risk_score for text that's actually a negative/distressed
# complaint dressed up in sarcastic "great, love that" framing.
SARCASM_OVERRIDE_THRESHOLD = 0.7

# Numbness/dissociation detection now lives in numbness_detector.py, using
# embedding similarity (SentenceTransformers) instead of regex, so it
# generalizes to phrasings not explicitly written into a keyword list.
# See that module's docstring for rationale and the dataset TODO.


def _top_result(raw) -> dict:
    """
    Normalizes HuggingFace pipeline output to a single {label, score} dict.

    With top_k=1 (or top_k=N generally), transformers wraps each input's
    result in an extra list: model(text) -> [[{"label":..., "score":...}]]
    So model(text)[0] is still a LIST, not the dict — this unwraps it
    safely regardless of whether an extra layer is present.
    """
    result = raw[0]
    if isinstance(result, list):
        result = result[0]
    return result


def run_sentiment(text: str) -> tuple[str, float]:
    """Returns (label, normalized_score ∈ [-1, 1])."""
    model = get_model("sentiment")
    result = _top_result(model(text))
    label_raw = result["label"].lower()
    conf = result["score"]
    label, direction = SENTIMENT_MAP.get(label_raw, ("neutral", 0.0))
    score = direction * conf
    return label, round(score, 4)


def run_emotion(text: str) -> tuple[str, float]:
    """Returns (emotion_label, confidence ∈ [0, 1])."""
    model = get_model("emotion")
    result = _top_result(model(text))
    label = result["label"].lower()
    label = EMOTION_LABELS.get(label, "neutral")
    return label, round(result["score"], 4)


def run_sarcasm(text: str) -> tuple[bool, float]:
    """Returns (is_sarcastic, confidence ∈ [0, 1])."""
    model = get_model("sarcasm")
    result = _top_result(model(text))
    is_irony = result["label"].lower() == "irony"
    return is_irony, round(result["score"], 4)


def resolve_effective_sentiment(
    sentiment_score: float,
    is_sarcastic: bool,
    sarcasm_score: float,
) -> tuple[float, str]:
    """
    Sarcasm frequently inverts the surface polarity of text — "Oh great,
    ANOTHER deadline moved up. Love that for me." reads as strongly
    positive to a sentiment model but means the opposite.

    When sarcasm is detected with high confidence AND it conflicts with
    the sentiment model's read (sentiment came back positive despite
    sarcastic framing), treat the effective sentiment as negative, scaled
    down slightly since the exact magnitude is less certain than a direct
    negative read would be.

    This deliberately does NOT touch sarcastic-but-negative text (sarcasm
    layered onto text that already reads negative) — only the
    positive+sarcastic conflict case, since that's the specific scenario
    where an uncorrected sentiment score would wrongly suppress risk_score
    and feed_score for what is often a genuine complaint.

    Returns (corrected_score, corrected_label).
    """
    if is_sarcastic and sarcasm_score >= SARCASM_OVERRIDE_THRESHOLD and sentiment_score > 0:
        corrected_score = round(-sentiment_score * 0.8, 4)
        return corrected_score, "negative"
    label = "negative" if sentiment_score < 0 else ("positive" if sentiment_score > 0 else "neutral")
    return sentiment_score, label


def compute_instant_risk(
    sentiment_score: float,
    emotion: str,
    emotion_score: float,
    is_sarcastic: bool,
    numbness_flagged: bool = False,
    numbness_strength: float = 0.0,
) -> float:
    """
    Heuristic instant risk score before LSTM.
    risk ∈ [0, 1]

    NOTE: sentiment_score passed in here should already be the corrected
    "effective" sentiment (see resolve_effective_sentiment), not the raw
    model output, so sarcasm-inverted positivity doesn't zero out the
    base risk term below.
    """
    # Base: negative sentiment pushes risk up
    base = max(0.0, -sentiment_score)  # 0–1

    # Emotion modifier
    emotion_weight = 0.0
    if emotion in NEGATIVE_EMOTIONS:
        emotion_weight = emotion_score * 0.4
    elif emotion in ("neutral", "surprise") and sentiment_score < -0.4:
        # Flat/neutral or surprised affect paired with clearly negative
        # sentiment is itself a pattern (masked distress, shock/confusion)
        # rather than an absence of signal — don't zero it out.
        emotion_weight = 0.15

    # Sarcasm can mask true negativity that the sentiment model still read
    # as ambiguous/neutral rather than clearly positive (the clearly-positive
    # case is now handled upstream by resolve_effective_sentiment). Keep a
    # small residual boost here for softer cases.
    sarcasm_boost = 0.1 if is_sarcastic and sentiment_score >= 0 else 0.0

    # Numbness/dissociation modifier — independent of the emotion classifier,
    # since flat affect often reports as "neutral" there.
    numbness_weight = numbness_strength * 0.35 if numbness_flagged else 0.0

    risk = min(1.0, base * 0.5 + emotion_weight + sarcasm_boost + numbness_weight)
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

    Hard-floor bypass: if detect_depression_suicide_risk() flags CRITICAL
    (explicit intent/means/farewell language), that overrides everything
    else — risk_score is forced to 1.0 and neither instant_risk's ML
    averaging nor the LSTM's temporal smoothing gets a chance to soften it.
    This is intentional per the project's hard-floor design principle:
    unambiguous high-risk signals must never be diluted.

    Sarcasm correction: sentiment_score/sentiment returned and stored here
    are the CORRECTED ("effective") values when sarcasm strongly
    contradicts a positive sentiment read — see resolve_effective_sentiment.
    This means the raw sentiment model's output is not separately retained;
    every downstream consumer (risk scoring, feed scoring, EmotionLog, etc.)
    sees the corrected value consistently.
    """
    raw_sentiment, raw_sentiment_score = run_sentiment(text)
    emotion, emotion_score     = run_emotion(text)
    is_sarcastic, sarcasm_score = run_sarcasm(text)
    numbness_flagged, numbness_strength = detect_numbness_signal(text)
    risk_detail = detect_depression_suicide_risk(text)

    sentiment_score, sentiment = resolve_effective_sentiment(
        raw_sentiment_score, is_sarcastic, sarcasm_score
    )
    if sentiment_score != raw_sentiment_score:
        logger.info(
            f"Sarcasm override — raw sentiment={raw_sentiment}({raw_sentiment_score}), "
            f"sarcasm_score={sarcasm_score} → corrected sentiment={sentiment}({sentiment_score})"
        )

    if risk_detail.hard_floor_triggered:
        logger.warning(
            f"HARD FLOOR triggered — matched phrase: {risk_detail.matched_phrase!r}. "
            f"Routing directly to CRITICAL tier, bypassing ML averaging."
        )
        risk_score = 1.0
        feed_score = compute_feed_score(sentiment_score, risk_score, likes_count, comments_count)
        return PipelineResult(
            sentiment=sentiment,
            sentiment_score=sentiment_score,
            emotion=emotion,
            emotion_score=emotion_score,
            sarcasm=is_sarcastic,
            sarcasm_score=sarcasm_score,
            numbness=numbness_flagged,
            numbness_score=numbness_strength,
            risk_score=risk_score,
            feed_score=feed_score,
        )

    instant_risk = compute_instant_risk(
        sentiment_score, emotion, emotion_score, is_sarcastic,
        numbness_flagged, numbness_strength,
    )

    # Fold in the graduated depression/suicide-risk tier (LOW/MODERATE/HIGH)
    # as an additional floor — instant_risk shouldn't be allowed to sit below
    # what this dedicated detector independently found.
    instant_risk = max(instant_risk, risk_detail.score)

    # LSTM temporal refinement
    history = (user_risk_history or []) + [instant_risk]
    lstm_risk = run_lstm_risk(history)

    # Blend instant + LSTM
    risk_score = round(instant_risk * 0.3 + lstm_risk * 0.7, 4) if lstm_risk > 0 else instant_risk

    feed_score = compute_feed_score(sentiment_score, risk_score, likes_count, comments_count)

    logger.debug(
        f"Pipeline → sentiment={sentiment}({sentiment_score}), "
        f"emotion={emotion}({emotion_score}), sarcasm={is_sarcastic}, "
        f"numbness={numbness_flagged}({numbness_strength}), "
        f"risk_tier={risk_detail.tier}({risk_detail.score}), "
        f"risk={risk_score}, feed={feed_score}"
    )

    return PipelineResult(
        sentiment=sentiment,
        sentiment_score=sentiment_score,
        emotion=emotion,
        emotion_score=emotion_score,
        sarcasm=is_sarcastic,
        sarcasm_score=sarcasm_score,
        numbness=numbness_flagged,
        numbness_score=numbness_strength,
        risk_score=risk_score,
        feed_score=feed_score,
    )