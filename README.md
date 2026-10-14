# FlowPilot

> Autonomous workflow agent that interprets natural-language scheduling goals, decomposes tasks, invokes tools against a SQLite-backed calendar, recovers from conflicts, and provides independent verification of persisted state.

---

## Key Features

1. **Natural-Language Mission Dispatcher**  
   Interprets complex scheduling goals (e.g., *"Plan tomorrow. I need two hours of DSA practice, three hours for my project, lunch, and a team meeting at 2 PM. Finish by 7 PM."*), extracting flexible tasks, fixed meetings, breaks, and deadlines.

2. **Deterministic & Production LLM Providers**  
   - **Deterministic Dev Mode (`FLOWPILOT_LLM_PROVIDER=dev`)**: Fully reproducible, offline, 100% testable planner without paid API keys.
   - **OpenAI-Compatible Mode (`FLOWPILOT_LLM_PROVIDER=openai`)**: Connects to OpenAI models (`gpt-4o-mini`, `gpt-4o`, etc.) using structured tool calling.

3. **Tool Registry & Execution Loop**  
   Strict schema validation across 9 core agent tools: `parse_goal`, `get_calendar`, `get_tasks`, `create_event`, `update_event`, `delete_event`, `find_free_slots`, `propose_schedule`, and `verify_schedule`. Bounded retries, deduplication, and max-step execution guards.

4. **Conflict Resolution & Recovery**  
   Detects calendar overlaps dynamically. If a required task conflicts with an existing non-fixed event, the agent recovers by deleting/moving the conflicting non-fixed item while strictly protecting immutable fixed events (e.g., team standups).

5. **Independent SQLite Verification**  
   An isolated verification engine queries the SQLite database directly, confirming all expected events are persisted without overlaps, within working hours (default 09:00–19:00 `Asia/Kolkata`), respecting duration and lunch breaks.

6. **Executive Web Dashboard**  
   Built with Vite + React + Vanilla CSS (dark-mode command center, glassmorphism, responsive grid, real-time tool trace feed, checklist inspector, and timeline view).

---

## Architecture

```
FlowPilot/
├── backend/
│   ├── app/
│   │   ├── agent/            # Execution loop, provider adapters, prompt engineering
│   │   ├── api/              # FastAPI endpoints (calendar, tasks, agent runs, verification)
│   │   ├── models/           # SQLAlchemy SQLite models (CalendarEvent, Task, AgentRun, etc.)
│   │   ├── schemas/          # Pydantic v2 validation models
│   │   ├── services/         # Scheduler, parser, seed data, and verification engine
│   │   ├── tools/            # Strict agent tool registry and tool handlers
│   │   ├── config.py         # Settings & environment variables
│   │   ├── db.py             # Database engine & session management
│   │   └── main.py           # FastAPI application entry point with CORS
│   └── tests/                # Comprehensive pytest suite (16 tests)
│
├── frontend/
│   ├── src/
│   │   ├── api/client.js     # Backend REST client with proxy & fallback
│   │   ├── components/       # Header, GoalComposer, TimelineCalendar, ExecutionTrace,
│   │   │                     # VerificationInspector, FinalReportCard, TaskBacklog, RunHistoryModal
│   │   ├── App.jsx           # Master dashboard view
│   │   └── index.css         # Foundational tokens, animations, and theme
│   └── vite.config.js        # Vite dev server with proxy to backend
│
├── .env.example              # Environment configuration template
└── PROJECT_PROGRESS.md       # Project milestone & test tracking
```

---

## Quick Start

### 1. Backend Setup

```bash
cd backend

# (Optional) Create virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run backend dev server
uvicorn app.main:app --reload --port 8000
```

The backend API will be available at `http://127.0.0.1:8000`.  
Interactive Swagger docs: `http://127.0.0.1:8000/docs`.

### 2. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start Vite dev server
npm run dev
```

Open `http://localhost:5173` in your browser.

---

## Configuration (`.env`)

Copy `.env.example` to `.env` or set environment variables:

| Variable | Default | Description |
|---|---|---|
| `FLOWPILOT_TIMEZONE` | `Asia/Kolkata` | Timezone context for scheduling (IST, UTC+5:30) |
| `FLOWPILOT_DATABASE_URL` | `sqlite:///./flowpilot.db` | SQLite database connection string |
| `FLOWPILOT_LLM_PROVIDER` | `dev` | `dev` for deterministic planner, `openai` for OpenAI API |
| `OPENAI_API_KEY` | *(empty)* | Required if provider is `openai` (or Gemini key) |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model name (e.g. `gpt-4o-mini`, `gemini-1.5-flash`, `gemini-2.0-flash`) |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Base URL (`https://generativelanguage.googleapis.com/v1beta/openai` for Gemini) |
| `FLOWPILOT_WORK_START` | `09:00` | Working hours start |
| `FLOWPILOT_WORK_END` | `19:00` | Working hours finish |
| `FLOWPILOT_LUNCH_START` | `12:00` | Lunch break start |
| `FLOWPILOT_LUNCH_END` | `13:00` | Lunch break finish |

---

## Running Backend Tests

```bash
cd backend
python -m pytest tests/ -v
```

Test suite coverage:
- `test_health.py`: Healthcheck, timezone reporting, and provider mode.
- `test_calendar_tasks.py`: Calendar CRUD, task listing, overlap rejection (409), fixed event protection (403).
- `test_scheduler.py`: Free slot discovery, impossible deadline detection, priority-based slot proposal.
- `test_agent.py`: Invalid tool call recovery, bounded tool retries, duplicate prevention, missing event detection, verification repair, end-to-end mission synthesis, conflict recovery.
