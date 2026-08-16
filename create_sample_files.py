import pandas as pd

sample_data = [
    {
        "TaskID": "PRJ-TASK-001",
        "Description": "HVAC Ductwork & Chiller Unit Installation",
        "ProjectDiscipline": "HVAC",
        "Priority": "High",
        "Risk": "High",
        "Hours": 120,
        "Created": "2026-08-01",
        "Target": "2026-08-15",
        "Status": "Open",
        "Location": "Building A - Level 3"
    },
    {
        "TaskID": "PRJ-TASK-002",
        "Description": "Main Electrical Panel Wiring & Transformer Load Test",
        "ProjectDiscipline": "Electrical",
        "Priority": "High",
        "Risk": "Medium",
        "Hours": 85,
        "Created": "2026-08-03",
        "Target": "2026-08-12",
        "Status": "Open",
        "Location": "Substation 2"
    },
    {
        "TaskID": "PRJ-TASK-003",
        "Description": "Structural Steel Column Reinforcement & Welding",
        "ProjectDiscipline": "Structural",
        "Priority": "Medium",
        "Risk": "High",
        "Hours": 160,
        "Created": "2026-08-02",
        "Target": "2026-08-20",
        "Status": "Open",
        "Location": "Podium Deck"
    },
    {
        "TaskID": "PRJ-TASK-004",
        "Description": "Plumbing Main Riser Hydrostatic Pressure Testing",
        "ProjectDiscipline": "Plumbing",
        "Priority": "Medium",
        "Risk": "Low",
        "Hours": 32,
        "Created": "2026-08-05",
        "Target": "2026-08-10",
        "Status": "Open",
        "Location": "Core Shaft West"
    },
    {
        "TaskID": "PRJ-TASK-005",
        "Description": "Architectural Drywall Partition Framing & Inspection",
        "ProjectDiscipline": "Architecture",
        "Priority": "Low",
        "Risk": "Low",
        "Hours": 45,
        "Created": "2026-08-04",
        "Target": "2026-08-14",
        "Status": "Open",
        "Location": "Level 1 Executive Lounge"
    },
    {
        "TaskID": "PRJ-TASK-006",
        "Description": "Foundation Concrete Pouring & Curing Audit",
        "ProjectDiscipline": "Civil",
        "Priority": "High",
        "Risk": "High",
        "Hours": 200,
        "Created": "2026-08-01",
        "Target": "2026-08-18",
        "Status": "Open",
        "Location": "Basement B2"
    },
    {
        "TaskID": "PRJ-TASK-007",
        "Description": "Fire Suppression Sprinkler Valve Calibration",
        "ProjectDiscipline": "Mechanical",
        "Priority": "Medium",
        "Risk": "Medium",
        "Hours": 50,
        "Created": "2026-08-06",
        "Target": "2026-08-13",
        "Status": "Open",
        "Location": "Mechanical Room 4"
    },
    {
        "TaskID": "PRJ-TASK-008",
        "Description": "BEMS Automation Controller Commissioning",
        "ProjectDiscipline": "Electrical",
        "Priority": "Low",
        "Risk": "Medium",
        "Hours": 64,
        "Created": "2026-08-05",
        "Target": "2026-08-16",
        "Status": "Open",
        "Location": "Control Center"
    }
]

df = pd.DataFrame(sample_data)
df.to_csv("sample_import_tasks.csv", index=False)
df.to_excel("sample_import_tasks.xlsx", index=False)

# Also place in public folder for direct download
df.to_csv("public/sample_import_tasks.csv", index=False)
df.to_excel("public/sample_import_tasks.xlsx", index=False)
print("Sample files created successfully!")
