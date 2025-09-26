
# Org Health Analyzer — Spans & Layers (Demo Prototype)

This repo powers a Streamlit app that analyzes **spans of control**, **layers**, and **potential redundancies** from a roster. It supports the **Employees** + **OrgEdges** layout in `synthetic_org_100.xlsx` and can also work with a single table that includes `ManagerID`.

## Quickstart (local)

```bash
# 1) Clone
git clone <your-repo-url>.git
cd org-health-analyzer

# 2) Create a virtual env (optional but recommended)
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3) Install deps
pip install -r requirements.txt

# 4) Run Streamlit
streamlit run app.py
```

Open the URL that Streamlit prints (typically http://localhost:8501), then **upload** `data/synthetic_org_100.xlsx` or your own roster.

## Deploy on Streamlit Community Cloud

1. Push this repo to GitHub.  
2. Go to https://share.streamlit.io → **New app** → pick your repo and set **Main file** to `app.py`.  
3. Click **Deploy**.  
4. Optional: Add your own `data/` file or instruct users to upload via the app.

## Data formats

### Option A — Multi‑sheet (recommended)
- **Employees**: `EmployeeID`, `FullName`, `JobRole`, `JobLevel`, `TeamID`, (optional) `ManagerID`
- **OrgEdges**: `EmployeeID`, `ManagerID` (one row per reporting relationship)
- **Principles** (optional): used to pre‑fill targets (e.g., span and layer guardrails)

### Option B — Single table
- One sheet or CSV with `EmployeeID`, `ManagerID`, and basic attributes. The app will compute spans/layers directly from this.

## What the app outputs
- KPI cards: headcount, % managers, average span, max depth
- Charts: histogram of spans, headcount by layer
- Tables: **Managers below min**, **managers above max**, **single‑report managers**, **duplicate titles** under the same manager
- Auto‑generated recommendations (rule‑based) you can copy into a deck

## Notes
- There is **no universal magic span**; tune thresholds by function and work complexity. Use the app’s sidebar to adjust targets during your demo. 
- Treat these outputs as **diagnostics** to **start conversations**—always validate with context (scope, geography, risk, regulatory constraints).

## Repo structure

```
org-health-analyzer/
├─ app.py
├─ requirements.txt
├─ README.md
├─ .gitignore
├─ .streamlit/
│  └─ config.toml
├─ data/
│  └─ synthetic_org_100.xlsx  # sample data for demo
└─ .github/workflows/
   └─ ci.yml                  # optional lint/run check
```

## Optional: CI check
The included GitHub Actions workflow runs a minimal import test to ensure `app.py` and required packages load.

---

### Credits
- Built for an MBA **Demonstration Prototype** assignment to show how AI/analytics can improve the reorg process (spans & layers).

