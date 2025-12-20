import os

# Detect if running locally and adjust path accordingly
if os.environ.get("RENDER") == "true":  # example env var for Render
    PERSISTENT_DIR = "/var/data"
else:
    # Local path inside your project folder
    PERSISTENT_DIR = os.path.join(os.getcwd(), "data")

os.makedirs(PERSISTENT_DIR, exist_ok=True)

USER_DB_FILE = os.path.join(PERSISTENT_DIR, "admin_users.db")
DB_FILE = os.path.join(PERSISTENT_DIR, "1st_year.db")
