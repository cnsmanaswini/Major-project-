"""
Unit tests for the adaptive feed ranking service.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from services.feed_service import (
    recency_score,
    compute_adaptive_rank,
    RECENCY_HALF_LIFE_HOURS,
    RISK_SUPPRESSION_THRESHOLD,
)


# ── recency_score ────────────────────────────────────────────

class TestRecencyScore:
    def test_brand_new_post_near_one(self):
        score = recency_score(datetime.utcnow())
        assert score > 0.95

    def test_half_life_approx_37_percent(self):
        old = datetime.utcnow() - timedelta(hours=RECENCY_HALF_LIFE_HOURS)
        score = recency_score(old)
        assert 0.30 <= score <= 0.45   # e^-1 ≈ 0.368

    def test_very_old_post_near_zero(self):
        old = datetime.utcnow() - timedelta(hours=RECENCY_HALF_LIFE_HOURS * 10)
        score = recency_score(old)
        assert score < 0.01

    def test_score_always_positive(self):
        for hours in [0, 1, 12, 24, 72, 168]:
            ts = datetime.utcnow() - timedelta(hours=hours)
            assert recency_score(ts) > 0


# ── compute_adaptive_rank ─────────────────────────────────────

def make_post(feed_score=0.7, risk_score=0.1, likes=20, comments=5, age_hours=1):
    post = MagicMock()
    post.feed_score    = feed_score
    post.risk_score    = risk_score
    post.likes_count   = likes
    post.comments_count = comments
    post.created_at    = datetime.utcnow() - timedelta(hours=age_hours)
    return post


class TestComputeAdaptiveRank:
    def test_result_in_unit_interval(self):
        post = make_post()
        score = compute_adaptive_rank(post, user_risk=0.0)
        assert 0.0 <= score <= 1.0

    def test_positive_post_outranks_negative_for_at_risk_user(self):
        good_post = make_post(feed_score=0.9, risk_score=0.05)
        bad_post  = make_post(feed_score=0.3, risk_score=0.75)
        user_risk = 0.8  # high-risk user

        good_rank = compute_adaptive_rank(good_post, user_risk)
        bad_rank  = compute_adaptive_rank(bad_post,  user_risk)
        assert good_rank > bad_rank

    def test_no_penalty_below_threshold(self):
        post = make_post(feed_score=0.5, risk_score=0.9)
        rank_safe = compute_adaptive_rank(post, user_risk=0.0)
        rank_low  = compute_adaptive_rank(post, user_risk=RISK_SUPPRESSION_THRESHOLD - 0.1)
        # Both below threshold — no penalty applied
        assert rank_safe == rank_low

    def test_penalty_applied_above_threshold(self):
        post = make_post(feed_score=0.5, risk_score=0.9)
        rank_safe  = compute_adaptive_rank(post, user_risk=RISK_SUPPRESSION_THRESHOLD - 0.1)
        rank_risky = compute_adaptive_rank(post, user_risk=RISK_SUPPRESSION_THRESHOLD + 0.1)
        assert rank_risky < rank_safe

    def test_high_engagement_boosts_rank(self):
        lo_eng = make_post(likes=0,   comments=0)
        hi_eng = make_post(likes=100, comments=50)
        assert compute_adaptive_rank(hi_eng, 0.0) > compute_adaptive_rank(lo_eng, 0.0)

    def test_fresh_post_outranks_stale_post(self):
        fresh = make_post(age_hours=0)
        stale = make_post(age_hours=72)
        assert compute_adaptive_rank(fresh, 0.0) > compute_adaptive_rank(stale, 0.0)

    def test_rank_never_negative(self):
        worst = make_post(feed_score=0.0, risk_score=1.0, likes=0, comments=0, age_hours=200)
        score = compute_adaptive_rank(worst, user_risk=1.0)
        assert score >= 0.0


# ── LSTM risk model ──────────────────────────────────────────

class TestLSTMRisk:
    def test_empty_history_returns_zero(self):
        from ai.pipeline.analyzer import run_lstm_risk
        with patch("ai.pipeline.analyzer.get_model") as mock_get:
            result = run_lstm_risk([])
        assert result == 0.0

    def test_single_value_history(self):
        import numpy as np
        mock_lstm = MagicMock()
        mock_lstm.predict = MagicMock(return_value=np.array([[0.35]]))
        with patch("ai.pipeline.analyzer.get_model", return_value=mock_lstm):
            from ai.pipeline.analyzer import run_lstm_risk
            result = run_lstm_risk([0.5])
        assert 0.0 <= result <= 1.0

    def test_long_history_truncated_to_20(self):
        import numpy as np
        mock_lstm = MagicMock()
        mock_lstm.predict = MagicMock(return_value=np.array([[0.6]]))
        with patch("ai.pipeline.analyzer.get_model", return_value=mock_lstm):
            from ai.pipeline.analyzer import run_lstm_risk
            long_history = [0.5] * 50
            result = run_lstm_risk(long_history)
        # Verify model was called with shape (1, 20, 1)
        call_args = mock_lstm.predict.call_args[0][0]
        assert call_args.shape == (1, 20, 1)

    def test_output_clamped_to_unit_interval(self):
        import numpy as np
        mock_lstm = MagicMock()
        # Simulate model returning out-of-range value
        mock_lstm.predict = MagicMock(return_value=np.array([[1.5]]))
        with patch("ai.pipeline.analyzer.get_model", return_value=mock_lstm):
            from ai.pipeline.analyzer import run_lstm_risk
            result = run_lstm_risk([0.7, 0.8, 0.9])
        assert result <= 1.0

    def test_high_risk_history_yields_high_prediction(self):
        import numpy as np
        mock_lstm = MagicMock()
        mock_lstm.predict = MagicMock(return_value=np.array([[0.82]]))
        with patch("ai.pipeline.analyzer.get_model", return_value=mock_lstm):
            from ai.pipeline.analyzer import run_lstm_risk
            result = run_lstm_risk([0.8] * 15)
        assert result > 0.5
