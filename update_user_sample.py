import pandas as pd
import shutil

src_path = "../SAMPLE DATA(Book2).csv"
df = pd.read_csv(src_path)
df = df.dropna(subset=["TaskID"]).reset_index(drop=True)

df.to_csv("sample_import_tasks.csv", index=False)
df.to_excel("sample_import_tasks.xlsx", index=False)

df.to_csv("public/sample_import_tasks.csv", index=False)
df.to_excel("public/sample_import_tasks.xlsx", index=False)

print(f"Updated sample files using user's SAMPLE DATA(Book2).csv ({len(df)} tasks).")
