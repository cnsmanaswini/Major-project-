# MindGram — System Architecture

## Overview

MindGram is a research-grade, mental health-aware social media platform that mirrors the interaction model of Instagram while layering a deep AI pipeline over every piece of user-generated content. The system is designed to be **modular**, **testable**, and **research-reproducible** — suitable as a final-year AI/ML major project.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          REACT FRONTEND (Vite + Tailwind)               │
│  Feed │ Reels │ Messages │ Dashboard │ Profile                          │
│  Adaptive content rendering · Intervention banners · Emotion badges     │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │ HTTP / JSON (Axios)
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         FASTAPI BACKEND                                 │
│                                                                         │
│  Routers:                                                               │
│  /api/posts  /api/feed  /api/messages  /api/analytics                   │
│  /api/interactions  /api/agents  /api/users                             │
│                                                                         │
│  Services:                                                              │
│  PostService · FeedService · AnalyticsService                           │
│                                                                         │
│  DB: SQLite via SQLAlchemy (async) → aiosqlite                          │
└────────────────┬─────────────────────────────────┬──────────────────────┘
                 │                                 │
                 ▼                                 ▼
┌───────────────────────────┐       ┌─────────────────────────────────────┐
│      AI PIPELINE          │       │          RAG SYSTEM                 │
│                           │       │                                     │
│  ① RoBERTa                │       │  FAISS flat-IP index                │
│     Sentiment (3-class)   │       │  all-MiniLM-L6-v2 embeddings        │
│                           │       │  20 curated MH knowledge docs       │
│  ② distilRoBERTa          │       │                                     │
│     Emotion (7-class)     │       │  query → cosine similarity →        │
│                           │       │  top-k supportive suggestions       │
│  ③ RoBERTa-irony          │       └─────────────────────────────────────┘
│     Sarcasm / irony       │                       ▲
│                           │                       │
│  ④ Keras LSTM             │       ┌───────────────┴─────────────────────┐
│     Temporal risk scoring │       │         AGENTIC AI SYSTEM           │
│     Input: seq(20) risks  │       │                                     │
│     Output: risk ∈ [0,1]  │       │  Agent 1: AnalyzerAgent             │
│                           │       │    → score vector from snapshot     │
│  ⑤ Feed Score             │       │                                     │
│     Weighted composite    │       │  Agent 2: ReflectionAgent           │
│     for ranking           │       │    → trajectory + streak analysis   │
└───────────────────────────┘       │                                     │
                                    │  Agent 3: DecisionAgent             │
                                    │    → risk level + action label      │
                                    │                                     │
                                    │  Agent 4: InterventionAgent         │
                                    │    → message + RAG retrieval        │
                                    └─────────────────────────────────────┘
```

---

## Component Details

### 1. Frontend (React + Tailwind CSS)

| Component | File | Description |
|-----------|------|-------------|
| App shell | `App.jsx` | Sidebar nav, routing, user context |
| Feed | `Feed/FeedPage.jsx` | Post creation, adaptive feed display, AI badge overlays |
| Reels | `Reels/ReelsPage.jsx` | Vertical video reel simulation |
| Messages | `Messages/MessagesPage.jsx` | Sentiment-colored DM threads |
| Dashboard | `Dashboard/DashboardPage.jsx` | Recharts sentiment + risk graphs |
| Profile | `Profile/ProfilePage.jsx` | Post grid with AI metadata, user risk strip |
| Badges | `Common/Badges.jsx` | `EmotionBadge`, `RiskBadge`, `SentimentBar`, `InterventionBanner` |

**Key design decisions:**
- All AI annotations (emotion, sentiment, sarcasm, risk) are overlaid on posts but hidden by default — users tap "AI" to expand them. This avoids overwhelming the interface while making the data inspectable.
- The `InterventionBanner` renders only when `risk_level` ≥ `moderate`. It surfaces the RAG suggestion inline in the feed.
- The dashboard uses Recharts `AreaChart` and `LineChart` with custom tooltips that render `EmotionBadge` inline.

---

### 2. Backend (FastAPI)

#### Routers

| Router | Prefix | Key operations |
|--------|--------|---------------|
| `posts.py` | `/api/posts` | `POST /` triggers full AI pipeline |
| `feed.py` | `/api/feed` | `GET /{user_id}` returns adaptive-ranked posts |
| `messages.py` | `/api/messages` | `POST /` analyzes sentiment; `GET /thread/{a}/{b}` |
| `analytics.py` | `/api/analytics` | `GET /{id}` full timeline; `GET /{id}/risk`; `GET /{id}/suggestions` |
| `interactions.py` | `/api/interactions` | `POST /` like/unlike; `POST /comment` adds comment + analyzes |
| `agents.py` | `/api/agents` | `GET /status/{id}` latest decision; `GET /history/{id}` |
| `users.py` | `/api/users` | CRUD operations |

#### Services

| Service | File | Purpose |
|---------|------|---------|
| PostService | `services/post_service.py` | Orchestrates AI + DB for post creation |
| FeedService | `services/feed_service.py` | Adaptive rank computation |
| AnalyticsService | `services/analytics_service.py` | Aggregates EmotionLog for dashboard |

#### Database Models (SQLAlchemy)

```
User ─────────────────────────────────────────────────
  id, username, display_name, avatar_url, bio

Post (annotated by AI pipeline) ──────────────────────
  id, user_id, content, image_url, is_reel
  sentiment, sentiment_score          ← RoBERTa
  emotion, emotion_score              ← distilRoBERTa
  sarcasm, sarcasm_score              ← RoBERTa-irony
  risk_score                          ← LSTM blend
  feed_score                          ← adaptive rank base

EmotionLog (temporal stream) ─────────────────────────
  id, user_id, timestamp
  sentiment_score, emotion, emotion_score, risk_score
  source (post | message | comment)
  agent_action                        ← written back by agent

AgentDecision ────────────────────────────────────────
  id, user_id, timestamp
  risk_level, decision, intervention, rag_suggestion
  metadata_json                       ← full agent trace
```

---

### 3. AI Pipeline

#### Stage 1 — Sentiment Analysis (RoBERTa)
- **Model:** `cardiffnlp/twitter-roberta-base-sentiment-latest`
- **Why this model:** Trained on ~124M tweets. Outperforms general-domain models on informal social media text, sarcasm-adjacent phrasing, and slang.
- **Output:** `LABEL_0` (negative) / `LABEL_1` (neutral) / `LABEL_2` (positive)
- **Normalization:** Score mapped to `[-1, +1]` preserving direction × confidence

#### Stage 2 — Emotion Detection (distilRoBERTa)
- **Model:** `j-hartmann/emotion-english-distilroberta-base`
- **Why this model:** Fine-tuned on 6 datasets covering 7 Ekman emotions. Strong F1 on social media and informal text.
- **Classes:** joy · sadness · anger · fear · disgust · surprise · neutral
- **Output:** Top class + confidence ∈ [0, 1]

#### Stage 3 — Sarcasm / Irony Detection (RoBERTa)
- **Model:** `cardiffnlp/twitter-roberta-base-irony`
- **Why needed:** Sarcastic positives ("Oh great, another rejection!") would otherwise score as positive sentiment, masking true risk. Sarcasm detection triggers a small but important risk boost on masked-positive posts.

#### Stage 4 — LSTM Temporal Risk Scoring (Keras)
- **Architecture:** LSTM(64) → Dropout(0.2) → LSTM(32) → Dropout(0.2) → Dense(16, ReLU) → Dense(1, sigmoid)
- **Input:** Sequence of 20 recent per-post risk scores (padded if fewer available)
- **Training data:** 8,000 synthetic sequences with 4 pattern types:
  - **Worsening:** Linear increase → label ~0.85
  - **Stable:** Low flat baseline → label = baseline
  - **Fluctuating:** Sinusoidal → label = mean of last 5
  - **Spike:** Sudden end-of-sequence peak → label ~0.80
- **Blending:** `final_risk = instant * 0.3 + lstm * 0.7`
  - The LSTM component is weighted higher because it incorporates temporal context. Instant risk provides recency signal when history is short.

#### Stage 5 — Feed Score Computation
```python
positivity  = (sentiment_score + 1.0) / 2.0    # [-1,1] → [0,1]
engagement  = min(1.0, (likes + 2*comments) / 100.0)
penalty     = risk_score * 0.6
feed_score  = positivity * 0.5 + engagement * 0.3 - penalty + 0.2 (baseline)
```

---

### 4. Adaptive Feed Re-ranking

Adaptive ranking runs in `FeedService.get_adaptive_feed()`:

```python
rank(post, user_risk) =
    post.feed_score   * 0.45     # AI quality score
  + recency_score()   * 0.30     # exponential decay (half-life = 24h)
  + engagement_score  * 0.25     # normalized likes + 2×comments / 50

# Mental health suppression (only when user_risk >= 0.6):
if user_risk >= 0.60 and post.risk_score > 0.5:
    penalty = (post.risk_score - 0.5) * user_risk * 0.4
    rank -= penalty
```

**Why this design:**
- The penalty is **gradual**, not binary. A post with risk_score=0.55 facing a user with risk=0.65 gets a small penalty (0.033). One with risk_score=0.95 facing a critical user (risk=0.92) gets a much larger penalty (0.185).
- It does **not** remove posts — only repositions them. The user retains access to all content, but positive/neutral content floats to the top.
- The threshold (0.60) aligns with the `high` risk level in the agent decision system.

---

### 5. Agentic AI System

The four agents form a **sequential decision pipeline**. Each agent outputs a structured object that feeds the next.

```
EmotionSnapshot
    ↓
AnalyzerAgent.analyze(snapshot)
    → {negativity, distress_flag, emotion, risk, source}
    ↓
ReflectionAgent.reflect(history, analysis)
    → {trajectory, streak, average_risk, history_length}
    ↓
DecisionAgent.decide(analysis, reflection)
    → (risk_level: str, decision: str)
    ↓
InterventionAgent.intervene(decision, emotion, sentiment_score, analysis)
    → (intervention_text: str, rag_suggestion: str)
    ↓
AgentReport
```

#### Risk Escalation Logic (DecisionAgent)

```python
effective_risk = current_risk

# Trajectory modifier
if trajectory == "worsening" and streak >= 3:
    effective_risk = min(1.0, effective_risk + 0.15)

# Chronic risk modifier
if average_risk > 0.6:
    effective_risk = min(1.0, effective_risk + 0.10)

# Thresholds
if effective_risk >= 0.80: return "critical", "escalate"
if effective_risk >= 0.60: return "high",     "suggest_resource"
if effective_risk >= 0.35: return "moderate",  "gentle_prompt"
else:                       return "low",       "monitor"
```

#### Intervention Levels

| Level | Decision | Frontend action |
|-------|----------|----------------|
| `low` | `monitor` | No UI change |
| `moderate` | `gentle_prompt` | Yellow wellness banner in feed |
| `high` | `suggest_resource` | Orange banner + resource cards |
| `critical` | `escalate` | Red crisis banner with helpline numbers |

---

### 6. RAG System

- **Embedder:** `all-MiniLM-L6-v2` (384-dim, fast, strong semantic similarity)
- **Index:** FAISS `IndexFlatIP` (inner product = cosine similarity on L2-normalized vectors)
- **Knowledge base:** 20 hand-curated mental health support entries covering:
  - Sadness / depression
  - Anxiety / panic
  - Anger
  - Fear / insecurity
  - Crisis / suicidal ideation
  - Positive reinforcement
  - Loneliness / social media
  - Sleep / burnout
  - Relationships / identity
- **Query construction:** `"{polarity} feeling {emotion} stress mental health"`
- **Retrieval:** Top-1 for post/message annotations; Top-3 for the dashboard suggestions panel
- **Crisis safety:** Two entries explicitly contain Indian helpline numbers (iCall, Vandrevala Foundation) and are surfaced when query context matches crisis keywords

---

## Data Flow: Post Creation

```
User submits post text
    ↓
POST /api/posts
    ↓
PostService.create_post_with_ai()
    ├─ analyze_text(content, risk_history)
    │      ├─ run_sentiment()     → RoBERTa
    │      ├─ run_emotion()       → distilRoBERTa
    │      ├─ run_sarcasm()       → RoBERTa-irony
    │      ├─ compute_instant_risk()
    │      ├─ run_lstm_risk()     → Keras LSTM
    │      └─ compute_feed_score()
    │      → PipelineResult
    │
    ├─ INSERT Post (with AI annotations)
    ├─ INSERT EmotionLog
    │
    ├─ run_agents(current_snapshot, emotion_history)
    │      ├─ AnalyzerAgent.analyze()
    │      ├─ ReflectionAgent.reflect()
    │      ├─ DecisionAgent.decide()
    │      └─ InterventionAgent.intervene()
    │             └─ retrieve_suggestion()  → FAISS RAG
    │      → AgentReport
    │
    ├─ INSERT AgentDecision
    ├─ UPDATE EmotionLog.agent_action
    └─ COMMIT
    ↓
Return PostOut (with all AI fields) → Frontend
```

---

## Research Design Notes

### Why RoBERTa over BERT?
RoBERTa removes the Next Sentence Prediction objective, trains with more data and larger batches, and consistently outperforms BERT on sentiment classification tasks (Liu et al., 2019). The Cardiff NLP Twitter variant is additionally domain-adapted on social media text, which closely matches MindGram's content.

### Why LSTM over Transformer for temporal risk?
Transformers have O(n²) attention complexity over the sequence. For our fixed-length (20-step) risk sequences with scalar inputs, an LSTM is faster to train, has fewer parameters (≈12K), and captures sequential dependencies effectively. A Transformer would offer minimal benefit at significant cost.

### Why FAISS flat index?
With only 20 documents, approximate nearest-neighbour search (IVF, HNSW) is unnecessary. `IndexFlatIP` performs exact inner-product search with L2-normalized vectors (equivalent to cosine similarity) and is optimal for small static corpora.

### Ethical design choices
1. **No binary decisions:** Risk scores are continuous, not hard cutoffs. Interventions are surfaced as gentle nudges, not alerts.
2. **Transparency:** All AI annotations are inspectable by the user (via the "AI" button on each post).
3. **No clinical claims:** All suggestions are general wellness content, not clinical advice.
4. **Helplines over diagnosis:** At high/critical risk, the system surfaces professional helpline numbers rather than attempting to "solve" the problem.
5. **Data locality:** SQLite is used deliberately — no external data transmission.

---

## Extension Ideas for Research

| Extension | Complexity | Value |
|-----------|-----------|-------|
| Multi-lingual support (Hindi/regional) | Medium | High for India context |
| Active learning loop (user feedback on suggestions) | Medium | Improves RAG relevance |
| Graph-based social risk propagation | High | Novel contribution |
| Federated learning for private model fine-tuning | High | Privacy-preserving |
| EEG/biometric signal integration (Raspberry Pi) | High | Multimodal risk model |
| BERT-based post summarisation for timeline | Low | Dashboard improvement |
| Explainability layer (LIME/SHAP on RoBERTa) | Medium | Interpretability chapter |
| Comparative study: RoBERTa vs GPT-4 sentiment | Low | Solid evaluation chapter |
