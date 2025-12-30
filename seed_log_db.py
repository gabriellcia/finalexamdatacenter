import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import random

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "log.db"
TBL = "system_log"

def ensure_table():
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {TBL} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                cpu REAL,
                memory REAL,
                disk REAL,
                ping_status TEXT,
                ping_ms REAL
            )
        """)
        conn.commit()

def seed(days=90, interval_minutes=60):
    ensure_table()
    end = datetime.now()
    start = end - timedelta(days=days)

    rows = []
    t = start
    while t <= end:
        cpu = round(random.uniform(5, 95), 2)
        mem = round(random.uniform(10, 98), 2)
        disk = round(random.uniform(20, 95), 2)
        ping_status = "OK" if random.random() > 0.05 else "FAIL"
        ping_ms = round(random.uniform(5, 80), 2) if ping_status == "OK" else None

        rows.append((t.strftime("%Y-%m-%d %H:%M:%S"), cpu, mem, disk, ping_status, ping_ms))
        t += timedelta(minutes=interval_minutes)

    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.executemany(
            f"INSERT INTO {TBL} (timestamp, cpu, memory, disk, ping_status, ping_ms) VALUES (?, ?, ?, ?, ?, ?)",
            rows
        )
        conn.commit()

    print(f"[OK] Seeded {len(rows)} rows into {DB_PATH} ({TBL})")

if __name__ == "__main__":
    seed(days=90, interval_minutes=60)
