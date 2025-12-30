import sqlite3
import os
import pandas as pd
import argparse
from datetime import datetime

DB_NAME_DEFAULT = "log.db"
TABLE_NAME_DEFAULT = "system_log"

# Auto-detect column names (kalau namanya beda-beda)
CANDIDATES = {
    "timestamp": ["timestamp", "time", "datetime", "created_at"],
    "cpu": ["cpu", "cpu_usage", "cpu_percent", "cpuPercentage"],
    "memory": ["memory", "mem", "ram", "memory_usage", "memory_percent", "ram_usage"],
    "disk": ["disk", "disk_usage", "disk_percent", "storage", "storage_usage"],
}

def pick_col(df_cols, candidates):
    for c in candidates:
        if c in df_cols:
            return c
    return None

def table_exists(conn, table_name: str) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table_name,))
    return cur.fetchone() is not None

def validate_range(series: pd.Series, min_v=0, max_v=100) -> int:
    s = pd.to_numeric(series, errors="coerce")
    invalid = s.isna() | (s < min_v) | (s > max_v)
    return int(invalid.sum())

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=DB_NAME_DEFAULT)
    parser.add_argument("--table", default=TABLE_NAME_DEFAULT)
    parser.add_argument("--save", default=None, help="optional: save report to txt file (e.g. test_report.txt)")
    args = parser.parse_args()

    report_lines = []
    report_lines.append("🔎 Running Full System Test...")
    report_lines.append(f"DB: {args.db}")
    report_lines.append(f"Table: {args.table}")
    report_lines.append("")

    # Step 1 - Verify DB exists
    if not os.path.exists(args.db):
        msg = "❌ Database not found. Please ensure 'log.db' exists."
        print(msg)
        report_lines.append(msg)
        if args.save:
            with open(args.save, "w", encoding="utf-8") as f:
                f.write("\n".join(report_lines))
        raise SystemExit(1)

    print("✅ Database file found.")
    report_lines.append("✅ Database file found.")

    # Step 2 - Check table + load
    try:
        conn = sqlite3.connect(args.db)

        if not table_exists(conn, args.table):
            msg = f"❌ Table '{args.table}' not found in {args.db}."
            print(msg)
            report_lines.append(msg)
            conn.close()
            raise SystemExit(1)

        df = pd.read_sql_query(f"SELECT * FROM {args.table};", conn)
        conn.close()

        print(f"✅ Loaded {len(df)} records from {args.table}.")
        report_lines.append(f"✅ Loaded {len(df)} records from {args.table}.")

        print("\n--- Preview (first 5 rows) ---")
        print(df.head())
        report_lines.append("\n--- Preview (first 5 rows) ---")
        report_lines.append(str(df.head()))

    except Exception as e:
        msg = f"❌ Database connection failed: {e}"
        print(msg)
        report_lines.append(msg)
        if args.save:
            with open(args.save, "w", encoding="utf-8") as f:
                f.write("\n".join(report_lines))
        raise SystemExit(1)

    # Step 3 - Detect columns
    cols = list(df.columns)
    colset = set(cols)

    ts_col = pick_col(colset, CANDIDATES["timestamp"])
    cpu_col = pick_col(colset, CANDIDATES["cpu"])
    mem_col = pick_col(colset, CANDIDATES["memory"])
    disk_col = pick_col(colset, CANDIDATES["disk"])  # optional

    print("\n✅ Column detection:")
    print(f"   timestamp -> {ts_col}")
    print(f"   cpu       -> {cpu_col}")
    print(f"   memory    -> {mem_col}")
    print(f"   disk(opt) -> {disk_col}")

    report_lines.append("\n✅ Column detection:")
    report_lines.append(f"timestamp -> {ts_col}")
    report_lines.append(f"cpu -> {cpu_col}")
    report_lines.append(f"memory -> {mem_col}")
    report_lines.append(f"disk(opt) -> {disk_col}")

    missing_required = []
    if ts_col is None: missing_required.append("timestamp")
    if cpu_col is None: missing_required.append("cpu")
    if mem_col is None: missing_required.append("memory")

    if missing_required:
        msg = f"\n❌ Missing required columns (auto-detect failed): {missing_required}\n➡️ Fix: rename columns or update CANDIDATES."
        print(msg)
        report_lines.append(msg)
        if args.save:
            with open(args.save, "w", encoding="utf-8") as f:
                f.write("\n".join(report_lines))
        raise SystemExit(1)

    print("\n✅ Column check passed.")
    report_lines.append("\n✅ Column check passed.")

    # Step 3b - Missing values
    missing_ts = int(df[ts_col].isna().sum())
    missing_cpu = int(df[cpu_col].isna().sum())
    missing_mem = int(df[mem_col].isna().sum())
    missing_disk = int(df[disk_col].isna().sum()) if disk_col else 0

    # Step 4 - Range validation (0–100)
    invalid_cpu = validate_range(df[cpu_col])
    invalid_mem = validate_range(df[mem_col])
    invalid_disk = validate_range(df[disk_col]) if disk_col else 0

    # Step 5 - Summary report
    summary = []
    summary.append("\n===== Test Summary =====")
    summary.append(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    summary.append(f"Records found: {len(df)}")
    summary.append(f"Missing timestamps: {missing_ts}")
    summary.append(f"Missing CPU values: {missing_cpu}")
    summary.append(f"Missing Memory values: {missing_mem}")
    if disk_col:
        summary.append(f"Missing Disk values: {missing_disk}")

    summary.append(f"Invalid CPU values (0-100): {invalid_cpu}")
    summary.append(f"Invalid Memory values (0-100): {invalid_mem}")
    if disk_col:
        summary.append(f"Invalid Disk values (0-100): {invalid_disk}")

    all_good = (
        missing_ts == 0 and
        invalid_cpu == 0 and
        invalid_mem == 0 and
        (invalid_disk == 0 if disk_col else True)
    )

    summary.append("\n🟢 System validation complete." if all_good else "\n🔴 System validation failed.")
    print("\n".join(summary))
    report_lines.extend(summary)

    # Optional save
    if args.save:
        with open(args.save, "w", encoding="utf-8") as f:
            f.write("\n".join(report_lines))
        print(f"\n📄 Report saved to: {args.save}")

    raise SystemExit(0 if all_good else 1)

if __name__ == "__main__":
    main()
