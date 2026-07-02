# 🧠 MindGram — Mental Health-Aware Social Media Platform

> A research-grade AI/ML final-year project simulating an Instagram-like social media platform with a deep mental health monitoring pipeline, adaptive feed curation, RAG-based suggestions, and agentic AI decision-making.

---

## 📁 Project Structure

```
mindgram/
├── frontend/                  # React + Tailwind CSS
│   ├── src/
│   │   ├── components/
│   │   │   ├── Feed/          # Post feed with adaptive ranking
│   │   │   ├── Reels/         # Short video reel simulation
│   │   │   ├── Messages/      # DM + sentiment-aware chat
│   │   │   ├── Dashboard/     # Emotional analytics dashboard
│   │   │   └── Common/        # Shared UI components
│   │   ├── hooks/             # Custom React hooks
│   │   ├── api/               # Axios API layer
│   │   └── utils/             # Helpers
│   └── package.json
│
├── backend/                   # FastAPI Python backend
│   ├── main.py                # App entry point
│   ├── routers/               # API route handlers
│   ├── models/                # SQLAlchemy DB models
│   ├── schemas/               # Pydantic schemas
│   ├── services/              # Business logic
│   └── ai/
│       ├── pipeline/          # Sentiment, Emotion, Sarcasm, LSTM
│       ├── agents/            # Agentic AI (Analyzer→Reflection→Decision→Intervention)
│       └── rag/               # FAISS + SentenceTransformers RAG
│
├── requirements.txt
├── docker-compose.yml
└── README.md
```

---

## 🚀 Installation & Setup

### Prerequisites
- Python 3.10+
- Node.js 18+
- pip, npm

### 1. Backend Setup

```bash
cd mindgram/backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r ../requirements.txt

# Download models (first run — takes ~5 min)
python -c "from ai.pipeline.loader import preload_models; preload_models()"

# Start backend
uvicorn main:app --reload --port 8000
```

### 2. Frontend Setup

```bash
cd mindgram/frontend
npm install
npm run dev
# Runs on http://localhost:5173
```

### 3. (Optional) Docker

```bash
docker-compose up --build
```

---

## 🧬 AI Pipeline Overview

```
User Post / Message
        │
        ▼
┌───────────────────┐
│  Sentiment (RoBERTa)│  → positive / negative / neutral
└───────────────────┘
        │
        ▼
┌───────────────────┐
│  Emotion Detection │  → joy / sadness / anger / fear / disgust / surprise
│  (distilroberta)  │
└───────────────────┘
        │
        ▼
┌───────────────────┐
│  Sarcasm Detection │  → sarcastic / genuine
│  (roberta-sarcasm)│
└───────────────────┘
        │
        ▼
┌───────────────────┐
│  LSTM Temporal    │  → emotional trajectory over time
│  Risk Scoring     │  → risk_score ∈ [0, 1]
└───────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│            AGENTIC AI SYSTEM            │
│  Analyzer → Reflection → Decision →    │
│  Intervention Agent                     │
└─────────────────────────────────────────┘
        │
        ▼
┌───────────────────┐
│  RAG (FAISS +     │  → Supportive mental health suggestion
│  SentenceTransf.) │
└───────────────────┘
        │
        ▼
   Adaptive Feed + Dashboard
```

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/posts` | Create a post (triggers AI pipeline) |
| GET | `/api/feed/{user_id}` | Get adaptive re-ranked feed |
| POST | `/api/messages` | Send a DM (with sentiment analysis) |
| GET | `/api/analytics/{user_id}` | Get emotional trend analytics |
| GET | `/api/suggestions/{user_id}` | Get RAG mental health suggestions |
| POST | `/api/interactions` | Record like/comment/share |
| GET | `/api/risk/{user_id}` | Get current mental health risk score |
| GET | `/api/agents/status/{user_id}` | Get agentic decision for user |

---

## 🔬 Research Notes

- **RoBERTa** (`cardiffnlp/twitter-roberta-base-sentiment`) for social-media-domain sentiment
- **Emotion** (`j-hartmann/emotion-english-distilroberta-base`) for 7-class emotion detection
- **LSTM** trained on temporal emotion sequences (synthetic + augmented data)
- **FAISS** flat L2 index with `all-MiniLM-L6-v2` sentence embeddings
- **Agentic loop**: Analyzer computes scores → Reflection evaluates trajectory → Decision determines action level → Intervention selects response type
- Feed re-ranking uses a weighted score: `final_score = engagement * 0.4 + positivity * 0.4 + recency * 0.2`

---

## ⚠️ Ethical Disclaimer

This is a research prototype. Mental health risk scores are **not clinical assessments**. No real user data is collected. All suggestions are general wellness resources. In production, professional clinical oversight is mandatory.
