# MindForge

Full-stack AI text intelligence platform: analyze documents (summary, sentiment, keywords, topics) and chat about them in context.

## Stack

| Layer    | Tech                                      |
| -------- | ----------------------------------------- |
| Backend  | Python, FastAPI, SQLAlchemy, SQLite       |
| AI       | TextBlob (local) + optional OpenAI GPT    |
| Frontend | React 19, TypeScript, Vite                |

## Features

- **Document management** — save, list, delete text documents
- **AI analysis** — summary, sentiment score, keywords, topics
- **Contextual chat** — ask questions grounded in your document
- **Dual AI mode** — works without API key (local NLP); add `OPENAI_API_KEY` for GPT

## Quick start

### 1. Backend

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
python -m textblob.download_corpora
copy .env.example .env   # optional: add OPENAI_API_KEY

uvicorn app.main:app --reload --port 8000
```

API docs: http://127.0.0.1:8000/docs

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

## Optional: OpenAI

Create `backend/.env`:

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

Without a key, the app uses local TextBlob-based analysis and retrieval-style chat.

## Project structure

```
project/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app
│   │   ├── models.py         # SQLAlchemy models
│   │   ├── routers/          # API routes
│   │   └── services/         # local + OpenAI AI logic
│   └── requirements.txt
└── frontend/
    └── src/
        ├── App.tsx           # Main UI
        └── api.ts            # API client
```

## API endpoints

| Method | Path                              | Description        |
| ------ | --------------------------------- | ------------------ |
| GET    | `/api/health`                     | Health & AI mode   |
| GET    | `/api/documents`                  | List documents     |
| POST   | `/api/documents`                  | Create document    |
| POST   | `/api/documents/{id}/analyze`     | Run AI analysis    |
| POST   | `/api/documents/{id}/chat`        | Chat with document |
| DELETE | `/api/documents/{id}`             | Delete document    |
