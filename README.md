# Week 12 – Log Analysis & Report Generation

## Objective

This week, you will analyze your monitored data stored in `log.db` and generate a simple **report** summarizing system performance and alerts.

---

## Data Source

Use the same `log.db` created in previous weeks (Week 7–11).  
If it is missing, re-run your logging scripts to generate new entries.

---

## Tasks

1. Load data from the `system_log` table in `log.db`
2. Display key statistics using Streamlit:
   - Average CPU / Memory / Disk usage
   - Number of alerts (CPU > 80%, MEM > 85%, DISK > 90%)
3. Create line charts for system resource trends
4. Add a **Download Report** button to export the summary as CSV

---

## Example Output

| Metric | Value |
|--------|--------|
| Average CPU | 27.54% |
| Average Memory | 42.10% |
| Average Disk | 59.23% |
| CPU Alerts | 3 |
| Memory Alerts | 1 |
| Disk Alerts | 0 |

---

## Submission Checklist

- [ ] `app.py` loads data and calculates statistics  
- [ ] Charts and metrics displayed correctly  
- [ ] CSV report can be downloaded  
- [ ] Screenshot showing your report page  
- [ ] Code pushed to GitHub

---

## Bonus (Optional)

- Add PDF export using `fpdf` or `reportlab`
- Add alert history table for the last 24 hours
- Display average Ping time as an additional metric
