import sqlite3
from pathlib import Path
import pandas as pd

# ======================
# PATH & TABLE CONFIG
# ======================
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "log.db"
SRC_TABLE = "system_log"

# Custom range (ubah sesuai kebutuhan)
CUSTOM_START = "2025-10-01"
CUSTOM_END   = "2025-12-30"

OUT_TABLES = {
    "all": "system_log_all",
    "7": "system_log_7d",
    "14": "system_log_14d",
    "30": "system_log_30d",
    "90": "system_log_90d",
    "custom": "system_log_custom",
}

# ======================
# DB HELPERS
# ======================
def ensure_db_exists():
    # SQLite akan membuat file db saat connect, tapi ini memperjelas
    if not DB_PATH.exists():
        DB_PATH.touch()

def ensure_source_table_exists():
    """
    Pastikan tabel system_log ada.
    Kalau kamu sudah punya tabel ini, aman (tidak mengubah apa-apa).
    """
    ensure_db_exists()
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {SRC_TABLE} (
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

def table_exists(conn, name: str) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1;", (name,))
    return cur.fetchone() is not None

def load_df() -> pd.DataFrame:
    """
    Load data dari system_log.
    """
    ensure_source_table_exists()

    with sqlite3.connect(str(DB_PATH)) as conn:
        if not table_exists(conn, SRC_TABLE):
            raise FileNotFoundError(f"Tabel sumber tidak ada: {SRC_TABLE}")

        df = pd.read_sql_query(f"SELECT * FROM {SRC_TABLE}", conn)

    if df.empty:
        return df

    if "timestamp" not in df.columns:
        raise ValueError("Kolom 'timestamp' tidak ada di system_log.")

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"]).copy()
    return df

def save_df(df: pd.DataFrame, table_name: str):
    """
    Simpan hasil filter ke table_name (replace).
    timestamp distandarkan jadi TEXT.
    """
    if df is None or df.empty:
        print(f"[SKIP] {table_name}: empty")
        return

    df_out = df.copy()
    df_out["timestamp"] = df_out["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")

    with sqlite3.connect(str(DB_PATH)) as conn:
        df_out.to_sql(table_name, conn, if_exists="replace", index=False)

    print(f"[OK] {table_name}: {len(df_out)} rows")

# ======================
# FILTERS (anchor by MAX timestamp)
# ======================
def filter_last_days(df: pd.DataFrame, days: int) -> pd.DataFrame:
    """
    Filter last N days dihitung dari timestamp TERBARU di data (max timestamp),
    supaya tidak kosong kalau log tidak up-to-date ke hari ini.
    """
    anchor = df["timestamp"].max()
    cutoff = anchor - pd.Timedelta(days=days)
    return df[df["timestamp"] >= cutoff].copy()

def filter_custom(df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    return df[(df["timestamp"] >= start_ts) & (df["timestamp"] <= end_ts)].copy()

def main():
    df = load_df()

    if df.empty:
        print("[WARN] system_log kosong. Tidak ada yang bisa difilter.")
        print("DB:", DB_PATH)
        return

    # ALL
    save_df(df, OUT_TABLES["all"])

    # 7/14/30/90
    for d in [7, 14, 30, 90]:
        df_d = filter_last_days(df, d)
        save_df(df_d, OUT_TABLES[str(d)])

    # CUSTOM
    df_c = filter_custom(df, CUSTOM_START, CUSTOM_END)
    save_df(df_c, OUT_TABLES["custom"])

    print("\nSource range:")
    print("MIN:", df["timestamp"].min())
    print("MAX:", df["timestamp"].max())
    print("DB :", DB_PATH)

if __name__ == "__main__":
    main()
