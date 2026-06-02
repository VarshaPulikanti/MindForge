# MindForge

Full-stack **local** text intelligence platform: upload or save documents, run analysis (summary, sentiment, keywords), and chat with RAG — no API keys required.

## Stack

| Layer    | Tech                                |
| -------- | ----------------------------------- |
| Backend  | Python, FastAPI, SQLAlchemy, SQLite |
| AI       | TextBlob, scikit-learn (TF-IDF RAG) |
| Frontend | React 19, TypeScript, Vite          |

## Features

- **Document management** — save, upload (.txt/.md/.csv), list, delete
- **AI analysis** — summary, sentiment, keywords, topics, metrics
- **RAG chat** — ask questions about the selected document
- **Fully offline** — runs on your machine, no cloud AI

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
```

**Windows (recommended)** — frees port 8000 if stuck, runs without `--reload`:

```powershell
.\run.ps1
```

**Or manually** (avoid `--reload` on Windows/OneDrive — it can hang):

```bash
uvicorn app.main:app --port 8000
```

API docs: http://127.0.0.1:8000/docs

Database is stored at `%LOCALAPPDATA%\MindForge\mindforge.db` (outside OneDrive to avoid locks).

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

## Project structure

```
project/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── routers/
│   │   └── services/      # local NLP + RAG
│   ├── run.ps1              # stable Windows start script
│   └── requirements.txt
└── frontend/
    └── src/
        ├── App.tsx
        └── api.ts
```

## API endpoints

| Method | Path                              | Description           |
| ------ | --------------------------------- | --------------------- |
| GET    | `/api/health`                     | Health & features     |
| GET    | `/api/documents`                  | List documents        |
| POST   | `/api/documents`                  | Create document       |
| POST   | `/api/documents/upload`           | Upload text file      |
| POST   | `/api/documents/{id}/analyze`     | Run AI analysis       |
| POST   | `/api/documents/{id}/chat`        | Chat with document    |
| DELETE | `/api/documents/{id}/messages`    | Clear chat history    |
| DELETE | `/api/documents/{id}`             | Delete document       |
