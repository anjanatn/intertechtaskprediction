import shutil
import os

shutil.copy("index.html", "web.html")
os.makedirs("public", exist_ok=True)
shutil.copy("index.html", "public/index.html")
shutil.copy("index.html", "public/web.html")
shutil.copy("intertech_n8n_workflow.json", "public/intertech_n8n_workflow.json")
print("Synced dashboard HTML and n8n workflow assets to public successfully!")
