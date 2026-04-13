import os

folders = [
    "app/api",
    "app/core",
    "app/db",
    "app/models",
    "app/schemas"
]

files = [
    ".env",
    "app/main.py",
    "app/api/endpoints.py",
    "app/db/session.py",
    "app/db/cache.py",  # [MAG-06] 캐싱 로직용
    "app/models/user.py",
    "app/schemas/magazine.py",
    "requirements.txt",
    "Dockerfile"
]

for f in folders: os.makedirs(f, exist_ok=True)
for f in files:
    if not os.path.exists(f):
        with open(f, "w", encoding="utf-8") as file: file.write("")
print("✅ Backend Repository Structure Ready!")