import csv

EMPLOYEES = [
    ("Rajan Mehta", 40),
    ("Asha Verma", 40),
    ("Dev Kapoor", 40),
    ("Priya Nair", 40),
    ("Suresh Kumar", 40),
    ("Meena Pillai", 30),
    ("Arjun Desai", 40),
    ("Lakshmi Iyer", 40),
]

csv_path = "simulated_project_delay_dataset_1000.csv"
with open(csv_path, "r", encoding="utf-8") as f:
    reader = list(csv.reader(f))

headers = reader[0]
if "AssignedTo" not in headers:
    headers.extend(["AssignedTo", "TeamCapacityHours"])
    for i, row in enumerate(reader[1:]):
        emp_name, emp_cap = EMPLOYEES[i % len(EMPLOYEES)]
        row.extend([emp_name, str(emp_cap)])

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(reader)
    print("Updated simulated_project_delay_dataset_1000.csv with AssignedTo and TeamCapacityHours")
else:
    print("simulated_project_delay_dataset_1000.csv already updated.")
