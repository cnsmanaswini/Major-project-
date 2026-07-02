#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  MindGram — One-Shot Setup Script
#  Usage: chmod +x setup.sh && ./setup.sh
# ─────────────────────────────────────────────────────────────

set -e

BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
CYAN="\033[36m"
RED="\033[31m"
RESET="\033[0m"

info()    { echo -e "${CYAN}[INFO]${RESET} $1"; }
success() { echo -e "${GREEN}[OK]${RESET}   $1"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET} $1"; }
error()   { echo -e "${RED}[ERR]${RESET}  $1"; exit 1; }

echo -e "${BOLD}╔══════════════════════════════════════════╗"
echo -e "║       MindGram — Setup Script            ║"
echo -e "║  Mental Health-Aware Social Media AI     ║"
echo -e "╚══════════════════════════════════════════╝${RESET}"
echo ""

# ── 0. Check prerequisites ───────────────────────────────────
info "Checking prerequisites..."

command -v python3 >/dev/null 2>&1 || error "Python 3.10+ required. Install from https://python.org"
command -v node    >/dev/null 2>&1 || error "Node.js 18+ required. Install from https://nodejs.org"
command -v npm     >/dev/null 2>&1 || error "npm required (comes with Node.js)"

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
NODE_VERSION=$(node --version | sed 's/v//')

info "Python: $PYTHON_VERSION  |  Node: $NODE_VERSION"

# ── 1. Backend virtual environment ──────────────────────────
info "Setting up Python virtual environment..."
cd backend

if [ ! -d "venv" ]; then
    python3 -m venv venv
    success "Virtual environment created."
else
    warn "Virtual environment already exists — skipping creation."
fi

source venv/bin/activate

# ── 2. Install Python dependencies ───────────────────────────
info "Installing Python dependencies (this may take 3–5 minutes)..."
pip install --upgrade pip -q
pip install -r ../requirements.txt -q
success "Python packages installed."

# ── 3. Pre-download AI models ────────────────────────────────
info "Pre-loading AI models from HuggingFace Hub (~1.5 GB first time)..."
echo "   Models: RoBERTa (sentiment) · distilRoBERTa (emotion)"
echo "           RoBERTa-irony (sarcasm) · MiniLM (RAG embeddings)"

python3 - <<'PYEOF'
import sys
print("  Downloading transformers models...")
try:
    from transformers import pipeline as hf_pipeline
    hf_pipeline("text-classification", model="cardiffnlp/twitter-roberta-base-sentiment-latest", truncation=True)
    hf_pipeline("text-classification", model="j-hartmann/emotion-english-distilroberta-base", truncation=True)
    hf_pipeline("text-classification", model="cardiffnlp/twitter-roberta-base-irony", truncation=True)
    print("  Transformers models ready.")
except Exception as e:
    print(f"  Warning: model download failed: {e}")
    print("  Models will be downloaded on first server start.")

print("  Downloading sentence-transformer...")
try:
    from sentence_transformers import SentenceTransformer
    SentenceTransformer("all-MiniLM-L6-v2")
    print("  Sentence-transformer ready.")
except Exception as e:
    print(f"  Warning: {e}")
PYEOF

# ── 4. Train LSTM model ───────────────────────────────────────
info "Training Keras LSTM risk model (synthetic data, ~2 min)..."
python3 - <<'PYEOF'
import sys, os
sys.path.insert(0, os.getcwd())
try:
    from ai.pipeline.lstm_risk import build_or_load_lstm
    model = build_or_load_lstm()
    print(f"  LSTM ready: {model.count_params()} parameters.")
except Exception as e:
    print(f"  Warning: LSTM training failed: {e}")
    print("  LSTM will fall back to instant risk scoring.")
PYEOF

# ── 5. Seed the database ──────────────────────────────────────
info "Seeding database with demo data..."
python3 seed.py
success "Database seeded."

deactivate
cd ..

# ── 6. Frontend dependencies ──────────────────────────────────
info "Installing frontend npm packages..."
cd frontend
npm install --silent
success "Frontend packages installed."
cd ..

# ── Done ─────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════╗"
echo -e "║          Setup complete! 🎉              ║"
echo -e "╚══════════════════════════════════════════╝${RESET}"
echo ""
echo -e "${BOLD}To start MindGram:${RESET}"
echo ""
echo -e "  ${CYAN}Terminal 1 — Backend:${RESET}"
echo -e "    cd backend"
echo -e "    source venv/bin/activate"
echo -e "    uvicorn main:app --reload --port 8000"
echo ""
echo -e "  ${CYAN}Terminal 2 — Frontend:${RESET}"
echo -e "    cd frontend"
echo -e "    npm run dev"
echo ""
echo -e "  ${CYAN}Open:${RESET} http://localhost:5173"
echo -e "  ${CYAN}API docs:${RESET} http://localhost:8000/docs"
echo ""
echo -e "  ${CYAN}Run tests:${RESET}"
echo -e "    cd backend && source venv/bin/activate && pytest"
echo ""
echo -e "${YELLOW}Note: First cold start takes ~30s while models load into memory.${RESET}"
