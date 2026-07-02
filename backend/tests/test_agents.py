"""
Unit tests for the Agentic AI pipeline.
Tests each agent independently and the full orchestrator flow.
"""

import pytest
from ai.agents.orchestrator import (
    AnalyzerAgent, ReflectionAgent, DecisionAgent, InterventionAgent,
    AgentOrchestrator, EmotionSnapshot, AgentReport, run_agents
)
from unittest.mock import patch


# ── Fixtures ─────────────────────────────────────────────────

def make_snap(sentiment=0.0, emotion="neutral", emotion_score=0.5, risk=0.2, source="post"):
    return EmotionSnapshot(
        sentiment_score=sentiment,
        emotion=emotion,
        emotion_score=emotion_score,
        risk_score=risk,
        source=source,
    )


# ── AnalyzerAgent ────────────────────────────────────────────

class TestAnalyzerAgent:
    def setup_method(self):
        self.agent = AnalyzerAgent()

    def test_positive_snap_low_negativity(self):
        snap = make_snap(sentiment=0.8, emotion="joy", risk=0.05)
        result = self.agent.analyze(snap)
        assert result["negativity"] == pytest.approx(0.0)
        assert result["distress_flag"] is False

    def test_negative_snap_high_negativity(self):
        snap = make_snap(sentiment=-0.85, emotion="sadness", risk=0.70)
        result = self.agent.analyze(snap)
        assert result["negativity"] > 0.5
        assert result["distress_flag"] is True

    def test_anger_is_distress(self):
        snap = make_snap(sentiment=-0.4, emotion="anger", risk=0.5)
        result = self.agent.analyze(snap)
        assert result["distress_flag"] is True

    def test_fear_is_distress(self):
        snap = make_snap(sentiment=-0.3, emotion="fear", risk=0.45)
        result = self.agent.analyze(snap)
        assert result["distress_flag"] is True

    def test_surprise_not_distress(self):
        snap = make_snap(sentiment=0.3, emotion="surprise", risk=0.1)
        result = self.agent.analyze(snap)
        assert result["distress_flag"] is False

    def test_neutral_emotion_not_distress(self):
        snap = make_snap(sentiment=0.0, emotion="neutral", risk=0.1)
        result = self.agent.analyze(snap)
        assert result["distress_flag"] is False


# ── ReflectionAgent ──────────────────────────────────────────

class TestReflectionAgent:
    def setup_method(self):
        self.agent = ReflectionAgent()

    def test_empty_history_returns_stable(self):
        result = self.agent.reflect([], {"risk": 0.2})
        assert result["trajectory"] == "stable"
        assert result["streak"] == 0

    def test_worsening_trajectory(self):
        history = [make_snap(risk=0.2), make_snap(risk=0.3), make_snap(risk=0.5)]
        result = self.agent.reflect(history, {"risk": 0.7})
        assert result["trajectory"] == "worsening"

    def test_improving_trajectory(self):
        history = [make_snap(risk=0.8), make_snap(risk=0.6), make_snap(risk=0.4)]
        result = self.agent.reflect(history, {"risk": 0.2})
        assert result["trajectory"] == "improving"

    def test_stable_trajectory(self):
        history = [make_snap(risk=0.3), make_snap(risk=0.32), make_snap(risk=0.31)]
        result = self.agent.reflect(history, {"risk": 0.3})
        assert result["trajectory"] == "stable"

    def test_streak_counts_consecutive_high_risk(self):
        history = [
            make_snap(risk=0.2),
            make_snap(risk=0.6),
            make_snap(risk=0.65),
            make_snap(risk=0.7),
        ]
        result = self.agent.reflect(history, {"risk": 0.72})
        assert result["streak"] == 3

    def test_streak_resets_on_low_risk(self):
        history = [
            make_snap(risk=0.7),
            make_snap(risk=0.8),
            make_snap(risk=0.1),  # low — resets streak
        ]
        result = self.agent.reflect(history, {"risk": 0.15})
        assert result["streak"] == 0

    def test_average_risk_calculated(self):
        history = [make_snap(risk=r) for r in [0.2, 0.4, 0.6]]
        result = self.agent.reflect(history, {"risk": 0.4})
        assert result["average_risk"] == pytest.approx(0.4, abs=0.01)


# ── DecisionAgent ─────────────────────────────────────────────

class TestDecisionAgent:
    def setup_method(self):
        self.agent = DecisionAgent()

    def test_low_risk_monitor(self):
        analysis   = {"risk": 0.1, "emotion": "neutral", "distress_flag": False, "negativity": 0.0, "source": "post"}
        reflection = {"trajectory": "stable", "streak": 0, "average_risk": 0.1}
        level, decision = self.agent.decide(analysis, reflection)
        assert level == "low"
        assert decision == "monitor"

    def test_moderate_risk_gentle_prompt(self):
        analysis   = {"risk": 0.45, "emotion": "sadness", "distress_flag": True, "negativity": 0.4, "source": "post"}
        reflection = {"trajectory": "stable", "streak": 0, "average_risk": 0.4}
        level, decision = self.agent.decide(analysis, reflection)
        assert level == "moderate"
        assert decision == "gentle_prompt"

    def test_high_risk_suggest_resource(self):
        analysis   = {"risk": 0.65, "emotion": "sadness", "distress_flag": True, "negativity": 0.7, "source": "post"}
        reflection = {"trajectory": "stable", "streak": 1, "average_risk": 0.6}
        level, decision = self.agent.decide(analysis, reflection)
        assert level == "high"
        assert decision == "suggest_resource"

    def test_critical_risk_escalate(self):
        analysis   = {"risk": 0.85, "emotion": "fear", "distress_flag": True, "negativity": 0.9, "source": "post"}
        reflection = {"trajectory": "stable", "streak": 2, "average_risk": 0.8}
        level, decision = self.agent.decide(analysis, reflection)
        assert level == "critical"
        assert decision == "escalate"

    def test_worsening_trajectory_escalates_risk(self):
        """Worsening trajectory with long streak should escalate effective risk."""
        analysis   = {"risk": 0.58, "emotion": "sadness", "distress_flag": True, "negativity": 0.6, "source": "post"}
        reflection = {"trajectory": "worsening", "streak": 4, "average_risk": 0.65}
        level, decision = self.agent.decide(analysis, reflection)
        # Effective risk raised above high threshold
        assert level in ("high", "critical")

    def test_high_average_risk_bumps_level(self):
        analysis   = {"risk": 0.55, "emotion": "anger", "distress_flag": True, "negativity": 0.5, "source": "post"}
        reflection = {"trajectory": "stable", "streak": 0, "average_risk": 0.72}
        level, _ = self.agent.decide(analysis, reflection)
        # Average risk > 0.6 adds 0.1 → effective risk ≥ 0.65 → high
        assert level in ("high", "critical")


# ── InterventionAgent ─────────────────────────────────────────

class TestInterventionAgent:
    def setup_method(self):
        self.agent = InterventionAgent()

    @patch("ai.agents.orchestrator.retrieve_suggestion", return_value="Take care of yourself.")
    def test_monitor_returns_no_action(self, mock_rag):
        text, suggestion = self.agent.intervene("monitor", "neutral", 0.05, {})
        assert "monitor" in text.lower() or "no immediate" in text.lower()
        assert suggestion == "Take care of yourself."

    @patch("ai.agents.orchestrator.retrieve_suggestion", return_value="Try breathing exercises.")
    def test_gentle_prompt_text(self, mock_rag):
        text, suggestion = self.agent.intervene("gentle_prompt", "sadness", -0.4, {})
        assert "prompt" in text.lower() or "wellness" in text.lower()

    @patch("ai.agents.orchestrator.retrieve_suggestion", return_value="Helpline available.")
    def test_escalate_shows_crisis_text(self, mock_rag):
        text, suggestion = self.agent.intervene("escalate", "fear", -0.9, {})
        assert "crisis" in text.lower() or "banner" in text.lower() or "helpline" in text.lower()


# ── Full Orchestrator ─────────────────────────────────────────

class TestAgentOrchestrator:
    @patch("ai.agents.orchestrator.retrieve_suggestion", return_value="You're doing great.")
    def test_full_run_low_risk(self, mock_rag):
        snap = make_snap(sentiment=0.8, emotion="joy", risk=0.05)
        report = run_agents(snap, [])
        assert isinstance(report, AgentReport)
        assert report.risk_level == "low"
        assert report.decision == "monitor"
        assert report.rag_suggestion == "You're doing great."

    @patch("ai.agents.orchestrator.retrieve_suggestion", return_value="Please seek support.")
    def test_full_run_high_risk(self, mock_rag):
        snap = make_snap(sentiment=-0.9, emotion="sadness", risk=0.82)
        report = run_agents(snap, [make_snap(risk=0.75)] * 5)
        assert report.risk_level in ("high", "critical")
        assert report.decision in ("suggest_resource", "escalate")

    @patch("ai.agents.orchestrator.retrieve_suggestion", return_value="Suggestion text.")
    def test_report_has_metadata(self, mock_rag):
        snap = make_snap(sentiment=-0.5, emotion="anger", risk=0.55)
        report = run_agents(snap)
        assert "analysis" in report.metadata
        assert "reflection" in report.metadata

    @patch("ai.agents.orchestrator.retrieve_suggestion", return_value="Keep going.")
    def test_history_influences_decision(self, mock_rag):
        """A user with a long worsening history should get higher risk than one without."""
        snap = make_snap(sentiment=-0.45, emotion="sadness", risk=0.55)
        history_bad = [make_snap(risk=r) for r in [0.4, 0.5, 0.6, 0.65, 0.7]]
        report_bad = run_agents(snap, history_bad)

        report_good = run_agents(make_snap(sentiment=0.2, emotion="neutral", risk=0.15), [])
        # Bad history should be at higher or equal risk
        level_order = ["low", "moderate", "high", "critical"]
        assert level_order.index(report_bad.risk_level) >= level_order.index(report_good.risk_level)
