"""
Agentic AI System for MindGram
Four-agent pipeline:
  1. AnalyzerAgent   — scores current emotional state
  2. ReflectionAgent — evaluates trajectory and patterns
  3. DecisionAgent   — determines risk level and action
  4. InterventionAgent — selects specific response + RAG suggestion
"""

import logging
from dataclasses import dataclass
from typing import List, Optional
from ai.rag.index import retrieve_suggestion

logger = logging.getLogger("mindgram.agents")


# ── Data Structures ──────────────────────────────────────────

@dataclass
class EmotionSnapshot:
    sentiment_score: float   # –1 to +1
    emotion: str
    emotion_score: float
    risk_score: float
    source: str = "post"


@dataclass
class AgentReport:
    risk_level: str          # low / moderate / high / critical
    decision: str            # monitor / gentle_prompt / suggest_resource / escalate
    intervention: str        # human-readable action label
    rag_suggestion: str      # retrieved supportive text
    metadata: dict


# ── Agent 1: Analyzer ───────────────────────────────────────

class AnalyzerAgent:
    """
    Synthesises the latest emotional snapshot into a structured score vector.
    """

    def analyze(self, snapshot: EmotionSnapshot) -> dict:
        negativity = max(0.0, -snapshot.sentiment_score)
        distress_flag = snapshot.emotion in {"sadness", "fear", "anger", "disgust"}

        return {
            "negativity": round(negativity, 3),
            "distress_flag": distress_flag,
            "emotion": snapshot.emotion,
            "risk": snapshot.risk_score,
            "source": snapshot.source,
        }


# ── Agent 2: Reflection ─────────────────────────────────────

class ReflectionAgent:
    """
    Reviews the last N emotional logs to detect trajectory.
    """

    def reflect(self, history: List[EmotionSnapshot], current: dict) -> dict:
        if not history:
            return {"trajectory": "stable", "streak": 0, "average_risk": current["risk"]}

        risks = [s.risk_score for s in history[-10:]]  # last 10
        avg = sum(risks) / len(risks)

        # Detect streak of high-risk entries
        streak = 0
        for r in reversed(risks):
            if r > 0.55:
                streak += 1
            else:
                break

        # Trajectory: is risk trending up?
        if len(risks) >= 3:
            recent = risks[-3:]
            if recent[-1] > recent[0] + 0.15:
                trajectory = "worsening"
            elif recent[-1] < recent[0] - 0.15:
                trajectory = "improving"
            else:
                trajectory = "stable"
        else:
            trajectory = "stable"

        return {
            "trajectory": trajectory,
            "streak": streak,
            "average_risk": round(avg, 3),
            "history_length": len(history),
        }


# ── Agent 3: Decision ────────────────────────────────────────

class DecisionAgent:
    """
    Determines risk level and chooses an action plan.
    """

    THRESHOLDS = {
        "critical": 0.80,
        "high":     0.60,
        "moderate": 0.35,
    }

    def decide(self, analysis: dict, reflection: dict) -> tuple[str, str]:
        risk = analysis["risk"]
        trajectory = reflection["trajectory"]
        streak = reflection["streak"]
        avg_risk = reflection["average_risk"]

        # Escalate if trajectory is worsening and streak is long
        effective_risk = risk
        if trajectory == "worsening" and streak >= 3:
            effective_risk = min(1.0, risk + 0.15)
        if avg_risk > 0.6:
            effective_risk = min(1.0, effective_risk + 0.1)

        if effective_risk >= self.THRESHOLDS["critical"]:
            return "critical", "escalate"
        elif effective_risk >= self.THRESHOLDS["high"]:
            return "high", "suggest_resource"
        elif effective_risk >= self.THRESHOLDS["moderate"]:
            return "moderate", "gentle_prompt"
        else:
            return "low", "monitor"


# ── Agent 4: Intervention ────────────────────────────────────

class InterventionAgent:
    """
    Selects the specific intervention message and triggers RAG retrieval.
    """

    INTERVENTIONS = {
        "monitor": "No immediate action needed. Continue monitoring emotional patterns.",
        "gentle_prompt": "Gently prompt user with a wellness check-in or mindfulness suggestion.",
        "suggest_resource": "Surface mental health resource cards and suggest a break from negative content.",
        "escalate": "Display a crisis support banner with helpline numbers prominently in the feed.",
    }

    def intervene(
        self,
        decision: str,
        emotion: str,
        sentiment_score: float,
        analysis: dict,
    ) -> tuple[str, str]:
        intervention_text = self.INTERVENTIONS.get(decision, "Monitor user.")

        # Build RAG query from emotional context
        polarity = "negative" if sentiment_score < -0.1 else "positive" if sentiment_score > 0.1 else "neutral"
        rag_query = f"{polarity} feeling {emotion} stress mental health"

        suggestion = retrieve_suggestion(rag_query)
        return intervention_text, suggestion


# ── Orchestrator ─────────────────────────────────────────────

class AgentOrchestrator:
    """Runs the full 4-agent pipeline."""

    def __init__(self):
        self.analyzer    = AnalyzerAgent()
        self.reflector   = ReflectionAgent()
        self.decider     = DecisionAgent()
        self.intervenor  = InterventionAgent()

    def run(
        self,
        current: EmotionSnapshot,
        history: Optional[List[EmotionSnapshot]] = None,
    ) -> AgentReport:
        history = history or []

        # Agent 1 — Analyze
        analysis = self.analyzer.analyze(current)
        logger.debug(f"AnalyzerAgent: {analysis}")

        # Agent 2 — Reflect
        reflection = self.reflector.reflect(history, analysis)
        logger.debug(f"ReflectionAgent: {reflection}")

        # Agent 3 — Decide
        risk_level, decision = self.decider.decide(analysis, reflection)
        logger.debug(f"DecisionAgent: risk={risk_level}, decision={decision}")

        # Agent 4 — Intervene
        intervention, rag_suggestion = self.intervenor.intervene(
            decision,
            current.emotion,
            current.sentiment_score,
            analysis,
        )
        logger.debug(f"InterventionAgent: {intervention[:60]}...")

        return AgentReport(
            risk_level=risk_level,
            decision=decision,
            intervention=intervention,
            rag_suggestion=rag_suggestion,
            metadata={
                "analysis": analysis,
                "reflection": reflection,
            },
        )


# Module-level singleton
_orchestrator = AgentOrchestrator()


def run_agents(
    current: EmotionSnapshot,
    history: Optional[List[EmotionSnapshot]] = None,
) -> AgentReport:
    return _orchestrator.run(current, history)
