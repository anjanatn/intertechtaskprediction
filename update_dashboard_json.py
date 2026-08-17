import json
import os
from datetime import datetime

EMPLOYEES = [
    {"name": "Rajan Mehta", "capacity": 40},
    {"name": "Asha Verma", "capacity": 40},
    {"name": "Dev Kapoor", "capacity": 40},
    {"name": "Priya Nair", "capacity": 40},
    {"name": "Suresh Kumar", "capacity": 40},
    {"name": "Meena Pillai", "capacity": 30},
    {"name": "Arjun Desai", "capacity": 40},
    {"name": "Lakshmi Iyer", "capacity": 40},
]

def update_json(filepath):
    if not os.path.exists(filepath):
        print(f"File {filepath} not found.")
        return
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    tasks = data.get("tasks", [])
    emp_map = {}

    for emp in EMPLOYEES:
        emp_map[emp["name"]] = {
            "name": emp["name"],
            "capacity": emp["capacity"],
            "openHours": 0.0,
            "closedHours": 0.0,
            "lastClosedDateStr": None,
            "lastClosedMs": 0,
            "hasMediumOpenTask": False
        }

    for i, t in enumerate(tasks):
        emp = EMPLOYEES[i % len(EMPLOYEES)]
        t["assigned_to"] = emp["name"]
        t["capacity_hours"] = emp["capacity"]

        name = emp["name"]
        status = str(t.get("status", "")).lower()
        hours = float(t.get("hours", 40.0) or 40.0)
        cat = str(t.get("cat", "LOW")).upper()

        if status in ["open", "in progress"]:
            emp_map[name]["openHours"] += hours
            if cat == "MEDIUM":
                emp_map[name]["hasMediumOpenTask"] = True
        elif status == "closed":
            emp_map[name]["closedHours"] += hours
            actual = str(t.get("actual_date", "") or "").strip()
            if actual and actual != "—":
                try:
                    clean_date = actual.split(" ")[0]
                    dt = datetime.strptime(clean_date, "%Y-%m-%d")
                    ms = int(dt.timestamp() * 1000)
                    if ms > emp_map[name]["lastClosedMs"]:
                        emp_map[name]["lastClosedMs"] = ms
                        emp_map[name]["lastClosedDateStr"] = clean_date
                except Exception:
                    pass

    data["employeeMap"] = emp_map

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"Updated {filepath} with {len(tasks)} tasks and {len(emp_map)} employees.")

update_json("dashboard_data.json")
if os.path.exists("public/dashboard_data.json"):
    update_json("public/dashboard_data.json")
