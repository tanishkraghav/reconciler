# Reconciler — Transaction Reconciliation System

A full-stack transaction reconciliation app:
- **Backend**: FastAPI (Python) — hosted on Render
- **Frontend**: Static HTML/JS — hosted on Vercel

---

## Project Structure

```
reconciler/
├── api/
│   ├── main.py            # FastAPI app
│   └── requirements.txt
├── frontend/
│   ├── index.html         # Dashboard UI
│   └── vercel.json
├── render.yaml            # Render deploy config
└── README.md
```

---

## Deploy: Backend on Render

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → **New** → **Web Service**
3. Connect your GitHub repo
4. Render will auto-detect `render.yaml` — click **Deploy**
5. Once live, copy your URL: `https://reconciler-api.onrender.com`

---

## Deploy: Frontend on Vercel

1. Go to [vercel.com](https://vercel.com) → **New Project**
2. Import the same GitHub repo
3. Set **Root Directory** to `frontend`
4. Click **Deploy**

### Connect frontend to backend

After Render gives you the API URL, open `frontend/index.html` and update line 1 of the `<script>`:

```js
const API_BASE = 'https://reconciler-api.onrender.com';
```

Redeploy (just push to GitHub — Vercel auto-deploys).

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/transactions` | List all (filter by `source`, `status`) |
| POST | `/transactions` | Add a transaction |
| DELETE | `/transactions/{id}` | Delete a transaction |
| POST | `/reconcile` | Run reconciliation engine |
| GET | `/ledger?source=bank` | Structured ledger with running balance |
| GET | `/summary` | Stats by status + category |
| POST | `/reset` | Restore demo seed data |

---

## Local Dev

```bash
# Backend
cd api
pip install -r requirements.txt
uvicorn main:app --reload
# → http://localhost:8000/docs

# Frontend — just open in browser
open frontend/index.html
```
