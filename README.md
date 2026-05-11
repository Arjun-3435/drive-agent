# 🗂️ DriveBot — Conversational AI for Google Drive

A fully conversational AI agent to search, filter, and discover files in Google Drive using natural language.

**Stack:** Python · FastAPI · LangGraph · LangChain · Groq (Llama 3.3 70B) · Google Drive API v3 · Streamlit

---

## 🚀 Local Setup (Step by Step)

### 1. Clone the repo
```bash
git clone https://github.com/your-username/drive-agent
cd drive-agent
```

### 2. Set up a Google Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use an existing one)
3. Enable the **Google Drive API**: APIs & Services → Library → search "Google Drive API" → Enable
4. Create a **Service Account**: APIs & Services → Credentials → Create Credentials → Service Account
   - Give it any name (e.g. `drive-agent-sa`)
   - Role: **Viewer** (read-only is enough)
5. After creating, go to the service account → **Keys** tab → Add Key → JSON
6. Download the JSON file → save it as `credentials/service_account.json`
7. Copy the service account email (looks like `xxx@xxx.iam.gserviceaccount.com`)

### 3. Share the Drive folder with your Service Account

1. Go to the [sample Drive folder](https://drive.google.com/drive/folders/1qkx58doSeYrcLjHPDysJyVJ36PsSqqlt)
2. Make a copy into your own Google Drive (Right-click → Make a copy)
3. Open your copied folder → Share → paste the service account email → Viewer → Send
4. Copy the folder ID from the URL (the long string after `/folders/`)

### 4. Get a Groq API key

1. Sign up at [console.groq.com](https://console.groq.com)
2. API Keys → Create API Key → copy it

### 5. Configure environment
```bash
cp .env.example .env
# Edit .env with your actual keys
```

### 6. Install dependencies & run backend
```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cd ..
uvicorn backend.main:app --reload --port 8000
```

### 7. Run frontend (new terminal)
```bash
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

Open http://localhost:8501 🎉

---

## ☁️ Cloud Deployment

### Backend → Railway

1. Push code to GitHub
2. New project on [Railway](https://railway.app) → Deploy from GitHub
3. Set environment variables:
   - `GROQ_API_KEY`
   - `GOOGLE_DRIVE_FOLDER_ID`
   - `SERVICE_ACCOUNT_B64` ← base64 of your JSON key:
```bash
     base64 -i credentials/service_account.json | tr -d '\n'
```
4. Railway uses `Procfile` automatically

### Frontend → Streamlit Community Cloud

1. Push frontend code to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) → New app
3. Set **Main file path**: `frontend/app.py`
4. Add **Secret**: `BACKEND_URL = https://your-railway-url.railway.app`

---

## 🧠 Agent Architecture

```
User Message
     │
     ▼
Streamlit (SSE consumer)
     │ POST /chat/stream
     ▼
FastAPI Backend
     │
     ▼
LangGraph ReAct Agent ─── MemorySaver (per-session state)
     │
     ├── Tool: search_drive_files(q_query)
     ├── Tool: list_all_files()
     └── Tool: get_file_details(file_id)
              │
              ▼
        Google Drive API v3
```

## 🔍 Query Examples the Agent Handles

| User Says | Drive Query Generated |
|---|---|
| "Find all PDFs" | `mimeType = 'application/pdf'` |
| "Search for budget files" | `name contains 'budget' or fullText contains 'budget'` |
| "Files from last week" | `modifiedTime > '2024-10-17T00:00:00'` |
| "Images in the drive" | `mimeType contains 'image/'` |
| "Find the financial report" | `name contains 'financial' and fullText contains 'report'` |