# AskHR — AI-Powered HR Assistant Chatbot

AskHR is an intelligent HR chatbot built with Flask, LangGraph, Google Gemini, and ChromaDB. Employees can log in with their credentials and ask natural-language questions about HR policies or their personal employment details — leave balances, salary, profile, and more.

---

## Features

- **Secure Login** — Authenticate with Employee ID, Name, and Password
- **Conversational Chat** — Ask anything about HR policies or your own records
- **RAG Pipeline** — Retrieves relevant policy context from a ChromaDB vector store
- **Employee Data Lookup** — Answers personal queries (leaves, salary, profile) directly from the employee database
- **LangGraph Routing** — Automatically routes queries to the right handler (policy RAG vs. employee DB)
- **Session-based Chat History** — Last 50 messages stored per user per session
- **Profile Page** — View your employee details in one place
- **Clean Responses** — All source/citation references are stripped from bot replies

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, Flask |
| LLM | Google Gemini (`gemini-2.5-flash`) |
| Vector DB | ChromaDB (persistent) |
| Embeddings | `sentence-transformers` (`all-MiniLM-L6-v2`) |
| Orchestration | LangGraph |
| Employee Data | Pandas (CSV-based) |
| Frontend | Jinja2 Templates, Bootstrap 5, Font Awesome |

---

## Project Structure

```
askhr/
├── app.py                  # Flask app — routes, session management, chat API
├── graph.py                # LangGraph workflow — router, employee node, policy node
├── utils.py                # Core logic — RAG retrieval, Gemini calls, auth validation
├── employee_db.py          # Employee CSV loader and query helpers
├── ingest.py               # Script to ingest HR policies into ChromaDB
├── requirements.txt        # Python dependencies
├── keys.env                # API keys and config (not committed)
├── data/
│   ├── employee.csv        # Employee records
│   └── hr_policies.txt     # HR policy documents (or .csv)
├── chroma_db/              # Persistent ChromaDB vector store (auto-created)
└── templates/
    ├── base.html
    ├── login.html
    ├── chat.html
    ├── profile.html
    └── error.html
```

---

## Setup & Installation

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/askhr.git
cd askhr
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate        # Linux/macOS
venv\Scripts\activate           # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure API Keys

Create a `keys.env` file in the project root:

```env
GEMINI_API_KEY=your_google_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-flash
EMBEDDING_MODEL=all-MiniLM-L6-v2
TOP_K=7
```

### 5. Prepare Data

**Employee CSV** — Create `data/employee.csv` with at least these columns:

```
Employee_Id, Name, Email, Password, Position, Department, Joining_Date,
Paid_Leave, Sick_Leave, Remaining_PL, Remaining_SL, Salary, Emp_Status
```

**HR Policies** — Create `data/hr_policies.txt` in the format:

```
PolicyName: Full policy description here.

AnotherPolicy: Another policy description.
```

Or use `data/hr_policies.csv` with `Policy` and `Description` columns.

### 6. Ingest HR Policies into ChromaDB

```bash
python ingest.py
```

This creates a persistent `chroma_db/` folder with your embedded policy documents.

### 7. Run the App

```bash
python app.py
```

Visit `http://127.0.0.1:5000` in your browser.

---

## How It Works

```
User Message
     │
     ▼
LangGraph Router
     │
     ├── Personal query? ("my leaves", "my salary")
     │        └──► Employee Node → Employee CSV lookup → Clean answer
     │
     └── General query? ("leave policy", "work from home")
              └──► Policy Node → ChromaDB retrieval → Gemini LLM → Clean answer
```

1. On login, the user's Employee ID, Name, and Password are verified against `employee.csv`.
2. Each chat message is passed to `run_hr_bot()` in `graph.py`.
3. The router node checks for personal keywords and routes accordingly.
4. Policy queries go through RAG: ChromaDB retrieves top-K policy chunks → Gemini generates a response.
5. All citations and source references are stripped before returning the response.

---

## API Endpoints

| Method | Route | Description |
|---|---|---|
| `GET/POST` | `/login` | Employee login |
| `GET` | `/logout` | Clear session and logout |
| `GET` | `/chat` | Chat interface |
| `POST` | `/api/chat` | Chat message handler (JSON) |
| `POST` | `/api/clear_chat` | Clear current user's chat history |
| `GET` | `/profile` | Employee profile page |
| `GET` | `/health` | Health check for all components |
| `GET` | `/debug` | Debug vector DB state (dev only) |

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | *(required)* | Google Gemini API key |
| `GEMINI_MODEL` | `gemini-1.5-flash` | Gemini model to use |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence transformer model |
| `TOP_K` | `7` | Number of policy chunks to retrieve |

---

## Notes

- `keys.env` and `chroma_db/` should be added to `.gitignore` — never commit API keys.
- Chat history is stored in-memory and resets on server restart. For persistence, replace the `chat_history` dict with a database.
- The `/debug` and `/api/check_employee/<emp_id>` routes should be removed or protected before production deployment.

---

## .gitignore Recommendation

```
keys.env
chroma_db/
__pycache__/
*.pyc
venv/
.env
```

---
