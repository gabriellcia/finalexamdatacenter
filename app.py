import os, sqlite3
from io import BytesIO
from datetime import datetime
import pandas as pd
import streamlit as st

DB, TBL = "log.db", "system_log"
st.set_page_config("Secure Dashboard + Log Analysis", layout="wide")

# ---------- Minimal PDF generator (no external libs) ----------
def pdf_bytes(lines):
    y, lh = 760, 14
    esc = lambda s: s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = "BT /F1 12 Tf " + " ".join(
        [f"1 0 0 1 50 {y-i*lh} Tm ({esc(l)}) Tj" for i, l in enumerate(lines)]
    ) + " ET"
    sb = stream.encode("latin-1")

    o = [
        b"%PDF-1.4\n",
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n",
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
        b"5 0 obj << /Length %d >> stream\n" % len(sb) + sb + b"\nendstream endobj\n",
    ]

    off, out = [], b""
    for p in o:
        off.append(len(out)); out += p
    xref_pos = len(out)
    xref = b"xref\n0 6\n0000000000 65535 f \n" + b"".join(
        [f"{off[i]:010d} 00000 n \n".encode() for i in range(1, 6)]
    )
    out += xref + b"trailer << /Size 6 /Root 1 0 R >>\nstartxref\n" + str(xref_pos).encode() + b"\n%%EOF"
    return out

# ---------- Data loader ----------
@st.cache_data(show_spinner=False)
def load_df():
    if not os.path.exists(DB):
        return pd.DataFrame()
    try:
        with sqlite3.connect(DB) as conn:
            df = pd.read_sql_query(f"SELECT * FROM {TBL}", conn)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        return df
    except Exception:
        return pd.DataFrame()

def stats_for(df):
    out = {}
    for k in ["cpu", "memory", "disk"]:
        if k in df.columns and len(df) > 0:
            out[k] = (float(df[k].mean()), float(df[k].max()), float(df[k].min()))
        else:
            out[k] = (0.0, 0.0, 0.0)
    return out

def highlight_alerts(df, thr):
    def _style(row):
        styles = []
        for col in row.index:
            if col in ["cpu", "memory", "disk"]:
                try:
                    styles.append("background-color:#ffd6d6" if float(row[col]) > thr[col] else "")
                except Exception:
                    styles.append("")
            else:
                styles.append("")
        return styles
    return df.style.apply(_style, axis=1)

def time_filter_ui(df):
    if "timestamp" not in df.columns:
        st.info("No timestamp column → filter waktu tidak tersedia.")
        return df, "All"

    df2 = df.dropna(subset=["timestamp"]).copy()
    if df2.empty:
        st.info("Timestamp tidak valid (semua NaT) → filter waktu tidak tersedia.")
        return df, "All"

    choice = st.selectbox("Filter waktu", ["All", "7 days", "14 days", "30 days", "90 days", "Custom"], index=2)
    if choice == "All":
        return df2, "All"

    if choice == "Custom":
        min_d = df2["timestamp"].min().date()
        max_d = df2["timestamp"].max().date()
        col1, col2 = st.columns(2)
        with col1:
            start = st.date_input("Start date", value=min_d, min_value=min_d, max_value=max_d)
        with col2:
            end = st.date_input("End date", value=max_d, min_value=min_d, max_value=max_d)

        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        f = df2[(df2["timestamp"] >= start_ts) & (df2["timestamp"] <= end_ts)]
        return f, f"Custom: {start} to {end}"

    days = int(choice.split()[0])
    cutoff = pd.Timestamp.now(tz=None) - pd.Timedelta(days=days)
    f = df2[df2["timestamp"] >= cutoff]
    return f, f"Last {days} days"

# ---------- Session defaults ----------
st.session_state.setdefault("logged_in", False)
st.session_state.setdefault("thr", {"cpu": 80, "memory": 85, "disk": 90})

# ---------- Login ----------
def login():
    st.title("🔐 Login")
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")
    if st.button("Login"):
        if u == "admin" and p == "admin123":
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("Invalid username or password.")

# ---------- Pages ----------
def page_dashboard(df):
    st.title("🌐 Secure Data Center Dashboard")

    if df.empty:
        st.warning("Database not found / table empty. Pastikan log.db dan tabel system_log ada.")
        return

    latest = df.iloc[-1]
    t = st.session_state.thr

    # KPI
    st.subheader("✅ KPI (Latest Reading)")
    c1, c2, c3 = st.columns(3)
    c1.metric("CPU (%)", f"{float(latest.get('cpu', 0)):.2f}", delta=f"thr {t['cpu']}%")
    c2.metric("Memory (%)", f"{float(latest.get('memory', 0)):.2f}", delta=f"thr {t['memory']}%")
    c3.metric("Disk (%)", f"{float(latest.get('disk', 0)):.2f}", delta=f"thr {t['disk']}%")

    # Status
    st.subheader("🚨 Status (Latest vs Threshold)")
    for k in ["cpu", "memory", "disk"]:
        if k not in df.columns:
            st.warning(f"Kolom '{k}' tidak ada di database.")
            continue
        msg = f"{k.upper()}: {latest[k]}% (threshold {t[k]}%)"
        (st.error if float(latest[k]) > t[k] else st.success)(msg)

    st.subheader("📊 Latest Logs (highlight alerts)")
    try:
        st.dataframe(highlight_alerts(df.tail(10), t), use_container_width=True)
    except Exception:
        st.dataframe(df.tail(10), use_container_width=True)

    st.subheader("📈 Resource Usage Over Time")
    trend_choice = st.selectbox("Trend view", ["All", "CPU only", "Memory only", "Disk only"], index=0, key="trend_dash")
    cols_map = {
        "All": ["cpu", "memory", "disk"],
        "CPU only": ["cpu"],
        "Memory only": ["memory"],
        "Disk only": ["disk"],
    }
    use_cols = cols_map[trend_choice]

    try:
        if "timestamp" in df.columns:
            plot = df.dropna(subset=["timestamp"]).set_index("timestamp")[use_cols]
        else:
            plot = df[use_cols]
        st.line_chart(plot)
    except Exception as e:
        st.warning(f"Could not plot chart: {e}")

def page_config():
    st.title("⚙️ Configuration Panel")
    t = st.session_state.thr
    t["cpu"] = st.slider("CPU Threshold (%)", 0, 100, int(t["cpu"]))
    t["memory"] = st.slider("Memory Threshold (%)", 0, 100, int(t["memory"]))
    t["disk"] = st.slider("Disk Threshold (%)", 0, 100, int(t["disk"]))
    if st.button("💾 Save"):
        st.session_state.thr = t
        st.success("Saved!")

def page_analysis(df):
    st.title("📊 Log Analysis & Reporting")

    if df.empty:
        st.warning("No data found.")
        return

    # Filter waktu
    with st.expander("🕒 Filter Waktu", expanded=True):
        df_f, label = time_filter_ui(df)
        st.caption(f"Filter: **{label}** | Rows: **{len(df_f)}**")

    if df_f.empty:
        st.warning("Hasil filter kosong. Coba pilih range yang lebih luas.")
        return

    t = st.session_state.thr
    tab1, tab2, tab3 = st.tabs(["📌 Overview", "📈 Trends", "📥 Reports"])

    # Overview
    with tab1:
        s = stats_for(df_f)
        st.subheader("📌 Key Statistics")
        c1, c2, c3 = st.columns(3)
        (a,b,c) = s["cpu"]; c1.metric("Avg CPU (%)", f"{a:.2f}"); c1.write(f"Max: {b:.2f}%"); c1.write(f"Min: {c:.2f}%")
        (a,b,c) = s["memory"]; c2.metric("Avg Memory (%)", f"{a:.2f}"); c2.write(f"Max: {b:.2f}%"); c2.write(f"Min: {c:.2f}%")
        (a,b,c) = s["disk"]; c3.metric("Avg Disk (%)", f"{a:.2f}"); c3.write(f"Max: {b:.2f}%"); c3.write(f"Min: {c:.2f}%")

        st.subheader("🚨 Alert Counts (Based on Current Thresholds)")
        a_cpu = int((df_f["cpu"] > t["cpu"]).sum()) if "cpu" in df_f.columns else 0
        a_mem = int((df_f["memory"] > t["memory"]).sum()) if "memory" in df_f.columns else 0
        a_disk = int((df_f["disk"] > t["disk"]).sum()) if "disk" in df_f.columns else 0
        x1, x2, x3 = st.columns(3)
        x1.metric(f"CPU > {t['cpu']}%", a_cpu)
        x2.metric(f"Memory > {t['memory']}%", a_mem)
        x3.metric(f"Disk > {t['disk']}%", a_disk)

        st.subheader("🧾 Sample Rows (Latest 10 in Filter) — highlight alerts")
        try:
            st.dataframe(highlight_alerts(df_f.tail(10), t), use_container_width=True)
        except Exception:
            st.dataframe(df_f.tail(10), use_container_width=True)

    # Trends
    with tab2:
        st.subheader("📈 CPU / Memory / Disk Trends")
        trend_choice = st.selectbox("Trend view", ["All", "CPU only", "Memory only", "Disk only"], index=0, key="trend_analysis")
        cols_map = {
            "All": ["cpu", "memory", "disk"],
            "CPU only": ["cpu"],
            "Memory only": ["memory"],
            "Disk only": ["disk"],
        }
        use_cols = cols_map[trend_choice]
        try:
            plot = df_f.set_index("timestamp")[use_cols] if "timestamp" in df_f.columns else df_f[use_cols]
            st.line_chart(plot)
        except Exception as e:
            st.warning(f"Could not plot chart: {e}")

    # Reports
    with tab3:
        st.subheader("📥 Download Reports")
        csv = df_f.to_csv(index=False).encode("utf-8")
        left, right = st.columns(2)
        left.download_button("⬇️ Download CSV", csv, "system_log_report.csv", "text/csv", use_container_width=True)

        if right.button("🧾 Generate PDF", use_container_width=True):
            gen = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            tr = "N/A"
            if "timestamp" in df_f.columns:
                try:
                    tr = f"{df_f['timestamp'].min()} to {df_f['timestamp'].max()}"
                except Exception:
                    pass

            s = stats_for(df_f)
            a_cpu = int((df_f["cpu"] > t["cpu"]).sum()) if "cpu" in df_f.columns else 0
            a_mem = int((df_f["memory"] > t["memory"]).sum()) if "memory" in df_f.columns else 0
            a_disk = int((df_f["disk"] > t["disk"]).sum()) if "disk" in df_f.columns else 0

            lines = [
                "System Log Analysis Report",
                "----------------------------------------",
                f"Generated at: {gen}",
                f"Filter: {label}",
                f"Rows: {len(df_f)}",
                f"Time range: {tr}",
                "",
                "Key Statistics:",
                f"CPU    avg={s['cpu'][0]:.2f}%  max={s['cpu'][1]:.2f}%  min={s['cpu'][2]:.2f}%",
                f"Memory avg={s['memory'][0]:.2f}%  max={s['memory'][1]:.2f}%  min={s['memory'][2]:.2f}%",
                f"Disk   avg={s['disk'][0]:.2f}%  max={s['disk'][1]:.2f}%  min={s['disk'][2]:.2f}%",
                "",
                "Thresholds:",
                f"CPU={t['cpu']}%  Memory={t['memory']}%  Disk={t['disk']}%",
                "Alert Counts:",
                f"CPU > {t['cpu']}%: {a_cpu}",
                f"Memory > {t['memory']}%: {a_mem}",
                f"Disk > {t['disk']}%: {a_disk}",
            ]
            right.download_button(
                "⬇️ Download PDF",
                BytesIO(pdf_bytes(lines)),
                "system_log_report.pdf",
                "application/pdf",
                use_container_width=True
            )

def do_logout():
    st.session_state.logged_in = False
    st.rerun()

# ---------- Main ----------
if not st.session_state.logged_in:
    login()
else:
    st.sidebar.title("📂 Navigation")

    # Refresh button
    if st.sidebar.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    page = st.sidebar.radio("Select Page", ["Dashboard", "Configuration", "Log Analysis & Report", "Logout"])
    df = load_df()

    if page == "Dashboard":
        page_dashboard(df)
    elif page == "Configuration":
        page_config()
    elif page == "Log Analysis & Report":
        page_analysis(df)
    else:
        do_logout()
