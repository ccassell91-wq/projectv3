
# app.py
# Org Health Analyzer — Spans & Layers
# Supports: Employees, OrgEdges, (optional) Principles sheets as in `synthetic_org_100.xlsx`

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from collections import defaultdict, deque

st.set_page_config(page_title="Org Health Analyzer — Spans & Layers", layout="wide")
st.title("🧠 Org Health Analyzer — Spans & Layers")
st.caption("Upload your roster (Excel/CSV). If present, the app will use an **OrgEdges** sheet for reporting lines and **Principles** for default targets.")

with st.sidebar:
    st.header("Upload")
    up = st.file_uploader("Upload Excel/CSV", type=["xlsx","xls","csv"]) 
    st.markdown("---")
    st.header("Targets (tune per context)")
    min_span = st.number_input("Min span target", 0, 50, 4)
    max_span = st.number_input("Max span target", 0, 100, 12)
    max_layers_target = st.number_input("Max layers target (head→frontline)", 1, 50, 6)
    st.markdown("---")
    st.caption("Tip: There is no single magic number for span—calibrate by role/work complexity.")

@st.cache_data(show_spinner=False)
def load_any(file):
    if file.name.lower().endswith('.csv'):
        df = pd.read_csv(file)
        return {'Employees': df}
    xl = pd.ExcelFile(file)
    sheets = {s: xl.parse(s) for s in xl.sheet_names}
    return sheets

# Helpers

def _standardize(df):
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].astype(str).str.strip()
    return df


def compute_metrics(sheets):
    # Try to find sheets by name fragment
    def pick(name):
        for k in sheets:
            if name.lower() in k.lower():
                return _standardize(sheets[k].copy())
        return None

    employees = pick('employees')
    edges = pick('orgedges')
    principles = pick('principles')

    if employees is None:
        st.error("No Employees sheet/table found. Include at least EmployeeID, FullName/Name, JobRole, ManagerID (or provide OrgEdges).")
        st.stop()

    # Ensure ID columns are strings
    employees['EmployeeID'] = employees['EmployeeID'].astype(str)
    if 'ManagerID' in employees.columns:
        employees['ManagerID'] = employees['ManagerID'].astype(str)

    # Choose reporting source
    if edges is not None:
        edges['EmployeeID'] = edges['EmployeeID'].astype(str)
        edges['ManagerID'] = edges['ManagerID'].astype(str)
        # Span from edges
        mgr_counts = edges.groupby('ManagerID')['EmployeeID'].count().rename('DirectReports')
    else:
        if 'ManagerID' not in employees.columns:
            st.error("No OrgEdges sheet and no ManagerID column in Employees.")
            st.stop()
        mgr_counts = employees.groupby('ManagerID')['EmployeeID'].count().rename('DirectReports')

    emp = employees.merge(mgr_counts, how='left', left_on='EmployeeID', right_index=True)
    emp['DirectReports'] = emp['DirectReports'].fillna(0).astype(int)
    emp['IsManager'] = emp['DirectReports'] > 0

    # Depth via BFS from roots
    if edges is not None:
        parent_of = defaultdict(set)
        for _, r in edges.iterrows():
            parent_of[r['ManagerID']].add(r['EmployeeID'])
        children = set(edges['EmployeeID'])
        parents = set(edges['ManagerID'])
        roots = sorted(list(parents - children)) or []
    else:
        parent_of = defaultdict(set)
        for _, r in employees.dropna(subset=['ManagerID']).iterrows():
            parent_of[r['ManagerID']].add(r['EmployeeID'])
        roots = emp.loc[~emp['ManagerID'].isin(emp['EmployeeID']), 'EmployeeID'].unique().tolist()

    depth = {eid: None for eid in emp['EmployeeID']}
    for r in roots:
        if r in depth and depth[r] is None:
            depth[r] = 0
        q = deque([r])
        while q:
            cur = q.popleft()
            for ch in parent_of.get(cur, []):
                if depth.get(ch) is None:
                    depth[ch] = (depth.get(cur, 0) or 0) + 1
                    q.append(ch)
    for k in depth:
        if depth[k] is None:
            depth[k] = 0
    emp['Depth'] = emp['EmployeeID'].map(depth).fillna(0).astype(int)

    # Use Principles (if available) to prefill targets once per session
    if principles is not None and st.session_state.get('_prefilled_from_principles', False) is False:
        try:
            p_span = principles[principles['Name'].str.contains('Span', case=False)].iloc[0]['TargetRule']
            # naive parse
            if isinstance(p_span, str) and '-' in p_span:
                left = p_span.split('-')[0]
                right = p_span.split('-')[1].split()[0]
                st.session_state['_min_span'] = int(''.join(filter(str.isdigit, left)))
                st.session_state['_max_span'] = int(''.join(filter(str.isdigit, right)))
        except Exception:
            pass
        try:
            p_layers = principles[principles['Name'].str.contains('Layer', case=False)].iloc[0]['TargetRule']
            nums = [int(s) for s in str(p_layers).split() if s.isdigit()]
            if nums:
                st.session_state['_max_layers'] = nums[0]
        except Exception:
            pass
        st.session_state['_prefilled_from_principles'] = True

    return emp, employees, edges


if up is None:
    st.info("Upload your file to get started. You can use the sample `data/synthetic_org_100.xlsx` from the repo.")
    st.stop()

sheets = load_any(up)
emp, employees_table, edges_table = compute_metrics(sheets)

# KPIs
n_people = len(emp)
manager_df = emp[emp['IsManager']]
n_managers = len(manager_df)
manager_ratio = (n_managers / n_people) if n_people else 0

avg_span = manager_df['DirectReports'].mean() if n_managers else 0
median_span = manager_df['DirectReports'].median() if n_managers else 0
min_observed = manager_df['DirectReports'].min() if n_managers else 0
max_observed = manager_df['DirectReports'].max() if n_managers else 0
max_depth = int(emp['Depth'].max())

# Flags
below_min = manager_df[manager_df['DirectReports'] < min_span]
above_max = manager_df[manager_df['DirectReports'] > max_span]
single_report = manager_df[manager_df['DirectReports'] == 1]

# Duplicate roles under same manager (if OrgEdges is present and Employees has JobRole)
if edges_table is not None and 'JobRole' in employees_table.columns:
    child_roles = edges_table.merge(employees_table[['EmployeeID','JobRole']], on='EmployeeID', how='left')
    dup_titles = (child_roles.groupby(['ManagerID','JobRole'])['EmployeeID']
                            .count().reset_index(name='Count'))
    dup_titles = dup_titles[dup_titles['Count'] >= 2].sort_values('Count', ascending=False)
else:
    dup_titles = pd.DataFrame(columns=['ManagerID','JobRole','Count'])

# Dashboard
k1, k2, k3, k4 = st.columns(4)
k1.metric("Headcount", f"{n_people:,}")
k2.metric("Managers", f"{n_managers:,}", delta=f"{manager_ratio:.0%} of org")
k3.metric("Avg span (managers)", f"{avg_span:.2f}", delta=f"median {median_span:.0f}")
k4.metric("Max depth (layers)", f"{max_depth}", delta=f"Target ≤ {max_layers_target}")

# Charts
c1, c2 = st.columns(2)
with c1:
    st.subheader("Distribution: direct reports per manager")
    if n_managers:
        fig = px.histogram(manager_df, x='DirectReports', nbins=15, opacity=0.9, color_discrete_sequence=['#2a9d8f'])
        fig.add_vline(x=min_span, line_dash='dash', line_color='orange', annotation_text=f"min {min_span}")
        fig.add_vline(x=max_span, line_dash='dash', line_color='red', annotation_text=f"max {max_span}")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.write("No managers detected.")

with c2:
    st.subheader("Headcount by layer (depth)")
    layers = emp.groupby('Depth')['EmployeeID'].count().reset_index(name='Headcount')
    fig2 = px.bar(layers, x='Depth', y='Headcount', color_discrete_sequence=['#264653'])
    fig2.add_vline(x=max_layers_target, line_dash='dash', line_color='red', annotation_text=f"target ≤ {max_layers_target}")
    st.plotly_chart(fig2, use_container_width=True)

st.subheader("Potential issues & opportunities")
colA, colB = st.columns(2)
with colA:
    st.write("**Managers below min span** (validate need)")
    st.dataframe(below_min[['EmployeeID', 'FullName' if 'FullName' in below_min.columns else 'EmployeeID', 'JobRole' if 'JobRole' in below_min.columns else 'IsManager', 'DirectReports']].reset_index(drop=True))
    st.write("**Managers above max span** (consider splitting)")
    st.dataframe(above_max[['EmployeeID', 'FullName' if 'FullName' in above_max.columns else 'EmployeeID', 'JobRole' if 'JobRole' in above_max.columns else 'IsManager', 'DirectReports']].reset_index(drop=True))

with colB:
    st.write("**Single‑report managers** (candidates to merge)")
    st.dataframe(single_report[['EmployeeID', 'FullName' if 'FullName' in single_report.columns else 'EmployeeID', 'JobRole' if 'JobRole' in single_report.columns else 'IsManager', 'DirectReports']].reset_index(drop=True))
    st.write("**Duplicate titles within same manager** (check redundancy)")
    st.dataframe(dup_titles.reset_index(drop=True))

# Auto recommendations (simple rules)
recs = []
if max_depth > max_layers_target:
    recs.append(f"Reduce layers: current max depth {max_depth} exceeds target {max_layers_target}; focus on middle layers for consolidation.")
for _, r in below_min.iterrows():
    nm = r.get('FullName', r['EmployeeID'])
    recs.append(f"{nm} has a narrow span of {int(r['DirectReports'])} (< {min_span}) — validate need for a distinct manager role or merge scope.")
for _, r in above_max.iterrows():
    nm = r.get('FullName', r['EmployeeID'])
    recs.append(f"{nm} has {int(r['DirectReports'])} direct reports (> {max_span}) — consider adding a lead layer or splitting scope.")
for _, r in dup_titles.head(20).iterrows():
    recs.append(f"Manager {r['ManagerID']} has {int(r['Count'])} '{r['JobRole']}' roles — assess overlap or broaden job scopes.")

st.subheader("Recommendations (auto‑generated)")
if recs:
    for r in recs[:50]:
        st.write("- ", r)
else:
    st.success("No major structural flags detected based on current thresholds.")

st.caption("Note: Directional diagnostic only. Tune thresholds by function and consider work complexity, decision rights, and risk before changing org design.")
