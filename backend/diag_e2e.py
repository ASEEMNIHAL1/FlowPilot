"""Quick diagnostic to understand e2e test failure"""
import json

import app.db as db_module
from app.config import get_settings, reset_settings_cache
from app.db import configure_engine, init_db
from app.main import create_app
from app.services.seed import reset_demo_data

import tempfile, os

# Setup test DB
tmp = tempfile.mkdtemp()
db_path = os.path.join(tmp, "diag.db")

os.environ["FLOWPILOT_DATABASE_URL"] = f"sqlite:///{db_path}"
os.environ["FLOWPILOT_LLM_PROVIDER"] = "dev"
os.environ["FLOWPILOT_TIMEZONE"] = "Asia/Kolkata"
os.environ["FLOWPILOT_INJECT_CREATE_FAILURES"] = "0"

reset_settings_cache()
settings = get_settings()
configure_engine(settings.database_url)
init_db()
db = db_module.SessionLocal()
reset_demo_data(db, settings)
db.close()

app = create_app()

from fastapi.testclient import TestClient
with TestClient(app) as client:
    SAMPLE_GOAL = (
        "Plan tomorrow. I need two hours of DSA practice, three hours for my project, "
        "lunch, and a team meeting at 2 PM. Finish by 7 PM."
    )
    response = client.post("/agent/run", json={"goal": SAMPLE_GOAL})
    body = response.json()
    print("STATUS CODE:", response.status_code)
    print("RUN STATUS:", body.get("status"))
    print("ERROR:", body.get("error_message"))
    print("FINAL REPORT:", json.dumps(body.get("final_report"), indent=2) if body.get("final_report") else "None")
    print("PARSED REQ date:", body.get("parsed_requirements", {}).get("date") if body.get("parsed_requirements") else "N/A")
    
    if body.get("id"):
        events = client.get(f"/agent/runs/{body['id']}/events")
        print("\nTOOL LOGS:")
        for item in events.json():
            print(f"  {item['tool_name']}: success={item['success']}, error={item.get('error')}")
