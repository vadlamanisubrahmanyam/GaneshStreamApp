"""
Standalone Supabase/Postgres connection test — completely independent of
app.py, Streamlit, and any caching. Run this directly:

    python test_db_connection.py

It reads DATABASE_URL from .env (same as the app does), tries to connect,
and prints a clear pass/fail with the actual error if it fails. Nothing
here depends on the rest of the GaneshStreamApp codebase.
"""
import os
import sys

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ DATABASE_URL is not set in your .env file.")
    sys.exit(1)

# Show the connection details being used, with the password masked, so you
# can visually confirm this script is reading what you think it's reading.
try:
    from sqlalchemy.engine import make_url
    url = make_url(DATABASE_URL)
    masked_password = ("*" * len(url.password)) if url.password else "(none)"
    print("Connecting with:")
    print(f"  user     = {url.username}")
    print(f"  password = {masked_password}  ({len(url.password) if url.password else 0} characters)")
    print(f"  host     = {url.host}")
    print(f"  port     = {url.port}")
    print(f"  database = {url.database}")
    print()
except Exception as e:
    print(f"❌ Couldn't even parse DATABASE_URL — check its format. Error: {e}")
    sys.exit(1)

try:
    import psycopg2

    conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
    cur = conn.cursor()
    cur.execute("SELECT current_database(), current_user, version();")
    db_name, db_user, version = cur.fetchone()
    print("✅ Connected successfully.")
    print(f"  current_database() = {db_name}")
    print(f"  current_user()     = {db_user}")
    print(f"  server version     = {version.splitlines()[0]}")
    cur.close()
    conn.close()
except Exception as e:
    print("❌ Connection failed.")
    print(f"  Error: {e}")
    sys.exit(1)
