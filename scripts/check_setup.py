"""
Day 1 check: run this to confirm everything is wired up.

    python -m scripts.check_setup

It (1) creates the database, (2) lists your Mesh models (free),
(3) makes one small chat call, (4) makes one image call.
"""
from app import db, mesh_client as mesh

print("1. Database:", db.DB_PATH)
tables = [r["name"] for r in db.fetch_all("SELECT name FROM sqlite_master WHERE type='table'")]
print("   tables:", ", ".join(tables))

print("2. Mesh models on your account:")
models = mesh.list_models()
print(f"   {len(models)} models found")
for wanted in (mesh.WRITER_MODEL, mesh.JUDGE_MODEL, mesh.IMAGE_MODEL):
    print(f"   {wanted}: {'FOUND' if wanted in models else 'NOT FOUND - pick another in .env'}")

print("3. Chat call...")
reply = mesh.chat([{"role": "user", "content": "Reply with exactly: Mesh is working"}], agent="setup_check")
print("   reply:", reply)

print("4. Image call...")
path = mesh.generate_image("A simple flat illustration of a pencil writing on paper, soft pastel colours",
                           agent="setup_check", filename="setup_check.png")
print("   saved:", path)

print("\nAll checks done.")
