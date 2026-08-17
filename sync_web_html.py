import shutil
import os

shutil.copy("index.html", "web.html")
os.makedirs("public", exist_ok=True)
shutil.copy("index.html", "public/index.html")
shutil.copy("index.html", "public/web.html")
print("Synced index.html to web.html, public/index.html, and public/web.html successfully!")
