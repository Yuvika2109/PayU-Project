import streamlit as st

st.set_page_config(
    page_title="FraudSynth | PayU",
    layout="wide",
    initial_sidebar_state="expanded",
)

CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    :root {
        --dark:   #00383D;
        --green:  #A6C307;
        --teal:   #005159;
        --bg:     #F5F7F5;
        --card:   #FFFFFF;
        --border: #DDE8DD;
        --text:   #1A2B1A;
        --muted:  #6A8A6A;
    }
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); }
    #MainMenu, footer, header { visibility: hidden; }
    .block-container { padding: 2rem 2.5rem !important; }

    [data-testid="stSidebar"] { background: var(--dark) !important; border-right: 2px solid var(--green); }
    [data-testid="stSidebar"] * { color: #fff !important; }

    .stButton > button { background: var(--green) !important; color: var(--dark) !important; font-weight: 600 !important; border: none !important; border-radius: 8px !important; padding: 10px 24px !important; }
    .stButton > button:hover { background: #B8D408 !important; }

    .stSelectbox > div > div, .stTextInput input, .stTextArea textarea, .stNumberInput input {
        border: 1px solid var(--border) !important; border-radius: 8px !important; background: #fff !important;
    }

    .card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 20px 24px; margin-bottom: 16px; }
    .card-title { font-size: 0.82rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.8px; color: var(--dark); border-bottom: 2px solid var(--green); padding-bottom: 8px; margin-bottom: 16px; display: inline-block; }

    .metric { background: var(--card); border: 1px solid var(--border); border-left: 4px solid var(--green); border-radius: 8px; padding: 14px 18px; }
    .metric.t { border-left-color: var(--teal); }
    .metric.w { border-left-color: #F57C00; }
    .metric.d { border-left-color: #D32F2F; }
    .metric .lbl { font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.8px; color: var(--muted); margin-bottom: 4px; }
    .metric .val { font-size: 1.7rem; font-weight: 700; color: var(--dark); line-height: 1.1; }
    .metric .sub { font-size: 0.72rem; color: var(--muted); margin-top: 4px; }

    .empty-state { background: #F9FBF9; border: 1.5px dashed var(--border); border-radius: 8px; padding: 32px 20px; text-align: center; }
    .empty-state .et { font-size: 0.92rem; font-weight: 600; color: var(--dark); margin-bottom: 6px; }
    .empty-state .ed { font-size: 0.8rem; color: var(--muted); line-height: 1.6; }

    .info { background: #E8F4F5; border-left: 3px solid var(--teal); padding: 10px 14px; border-radius: 0 6px 6px 0; font-size: 0.82rem; color: var(--dark); margin-bottom: 12px; }

    .tag { display:inline-block; background:#E8F4F5; color:var(--teal); font-size:0.7rem; font-weight:600; padding:2px 8px; border-radius:20px; border:1px solid #B0D8DC; }
    .tag.w { background:#FFF3E0; color:#E65100; border-color:#FFCC80; }

    .flabel { font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.7px; color: var(--muted); margin: 14px 0 4px; }

    .section-divider { border: none; border-top: 1px solid var(--border); margin: 18px 0; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ── Helpers ────────────────────────────────────────────────────────────────────
def empty(title, desc):
    st.markdown(f'<div class="empty-state"><div class="et">{title}</div><div class="ed">{desc}</div></div>', unsafe_allow_html=True)

def info(text):
    st.markdown(f'<div class="info">{text}</div>', unsafe_allow_html=True)

def metric(label, val, sub="", kind=""):
    st.markdown(f'<div class="metric {kind}"><div class="lbl">{label}</div><div class="val">{val}</div><div class="sub">{sub}</div></div>', unsafe_allow_html=True)

def fl(text):
    st.markdown(f'<div class="flabel">{text}</div>', unsafe_allow_html=True)


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding:24px 0 20px;text-align:center;">
        <div style="font-size:1.3rem;font-weight:800;color:#fff;letter-spacing:-0.5px;">FraudSynth</div>
        <div style="font-size:0.68rem;color:#A6C307;letter-spacing:1.2px;text-transform:uppercase;margin-top:3px;">PayU Risk Intelligence</div>
    </div>
    <hr style="border-color:rgba(166,195,7,0.25);margin:0 0 16px;">
    <div style="font-size:0.65rem;text-transform:uppercase;letter-spacing:1px;color:#7AADAD;margin-bottom:8px;">Menu</div>
    """, unsafe_allow_html=True)

    page = st.radio("", [
        "Dashboard",
        "Simulate",
        "Reports and Metrics",
        "About",
    ], label_visibility="collapsed")

    st.markdown("""
    <hr style="border-color:rgba(166,195,7,0.25);margin:16px 0;">
    <div style="font-size:0.65rem;text-transform:uppercase;letter-spacing:1px;color:#7AADAD;margin-bottom:10px;">System Status</div>
    <div style="font-size:0.78rem;color:#C8E8C8;line-height:2.2;">
        <span style="color:#A6C307;font-weight:700;">&#8226;</span>&nbsp; Ollama — Connecting<br>
        <span style="color:#A6C307;font-weight:700;">&#8226;</span>&nbsp; Llama 3 — Ready<br>
        <span style="color:#F57C00;font-weight:700;">&#8226;</span>&nbsp; Dataset — Not Generated
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
if page == "Dashboard":
    st.title("Dashboard")
    st.caption("Overview of synthetic dataset generation and rule simulation activity.")
    st.divider()

    c1, c2, c3, c4 = st.columns(4)
    with c1: metric("Datasets Generated", "—", "No runs yet")
    with c2: metric("Rules Simulated",    "—", "No runs yet", "t")
    with c3: metric("Avg Precision",      "—", "Run a simulation first", "w")
    with c4: metric("Avg Recall",         "—", "Run a simulation first", "d")

    st.markdown("<br>", unsafe_allow_html=True)
    col_l, col_r = st.columns([3, 2], gap="large")

    with col_l:
        st.markdown('<div class="card"><div class="card-title">Recent Activity</div>', unsafe_allow_html=True)
        empty("No Simulations Run Yet",
              "Go to Simulate, describe a fraud scenario, enter a detection rule, set parameters, and click Run.")
        st.markdown('</div>', unsafe_allow_html=True)

    with col_r:
        st.markdown('<div class="card"><div class="card-title">Example Scenarios</div>', unsafe_allow_html=True)
        for name, desc in [
            ("BIN Attack",       "Multiple cards with same BIN tested rapidly"),
            ("Account Takeover", "Unauthorized access with unusual spend"),
            ("Card Testing",     "Small amounts to verify card validity"),
            ("Velocity Abuse",   "Same card used excessively at one merchant"),
        ]:
            st.markdown(f"""
            <div style="padding:8px 0;border-bottom:1px solid #EEF2EE;">
                <span style="font-weight:600;font-size:0.85rem;color:#00383D;">{name}</span>
                <span style="font-size:0.78rem;color:#6A8A6A;margin-left:8px;">{desc}</span>
            </div>""", unsafe_allow_html=True)
        st.markdown('<div style="font-size:0.73rem;color:#6A8A6A;margin-top:10px;font-style:italic;">Any fraud scenario can be described in plain text.</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="card"><div class="card-title">How To Use</div>', unsafe_allow_html=True)
    s1, s2, s3 = st.columns(3)
    for col, num, title, desc in [
        (s1, "01", "Describe, Configure & Run", "Go to Simulate. Type any fraud scenario, enter your detection rule, set volume and fraud ratio — all in one place."),
        (s2, "02", "Dataset + Rule Applied",    "The system generates a labeled dataset and immediately applies your rule to every transaction row."),
        (s3, "03", "Review Metrics",            "Go to Reports and Metrics to see Precision, Recall, F1, and the full confusion matrix."),
    ]:
        with col:
            st.markdown(f"""
            <div style="background:#F5F7F5;border-radius:8px;padding:16px;border-top:2px solid #A6C307;">
                <div style="font-size:0.65rem;font-weight:700;color:#A6C307;letter-spacing:1.5px;margin-bottom:6px;">STEP {num}</div>
                <div style="font-weight:600;font-size:0.87rem;color:#00383D;margin-bottom:6px;">{title}</div>
                <div style="font-size:0.79rem;color:#6A8A6A;line-height:1.6;">{desc}</div>
            </div>""", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SIMULATE  (Scenario + Rule + Parameters — all together)
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Simulate":
    st.title("Simulate")
    st.caption("Describe a fraud scenario, enter a detection rule, and configure parameters — then run everything together.")
    st.divider()

    col_l, col_r = st.columns([2, 3], gap="large")

    with col_l:

        # ── 1. Scenario ──────────────────────────────────────────────────────
        st.markdown('<div class="card"><div class="card-title">1 — Fraud Scenario</div>', unsafe_allow_html=True)
        fl("Describe the fraud scenario")
        st.text_area(
            "",
            placeholder="e.g. BIN attack where fraudsters rapidly test multiple cards sharing the same BIN prefix with small transaction amounts across different merchants...",
            height=110,
            label_visibility="collapsed",
            key="scenario_input"
        )
        st.markdown("""
        <div style="font-size:0.73rem;color:#6A8A6A;margin-top:6px;">
            Examples: BIN Attack &nbsp;|&nbsp; Account Takeover &nbsp;|&nbsp; Card Testing &nbsp;|&nbsp; Velocity Abuse &nbsp;|&nbsp; Identity Theft
        </div>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # ── 2. Rule ──────────────────────────────────────────────────────────
        st.markdown('<div class="card"><div class="card-title">2 — Detection Rule</div>', unsafe_allow_html=True)
        fl("Rule condition")
        st.text_area(
            "",
            placeholder="e.g. number_of_transactions(card_id, last_3_days) > 40",
            height=75,
            label_visibility="collapsed",
            key="rule_input"
        )
        info("The rule will be applied to every transaction row. A rule_triggered column (True / False) will be added to the dataset.")

        fl("Rule Type")
        rule_type = st.selectbox("", [
            "Velocity — Transaction count by card in time window",
            "Amount  — Single transaction exceeds threshold",
            "BIN     — Unique cards on same BIN in time window",
        ], label_visibility="collapsed")

        if "Velocity" in rule_type:
            c1, c2 = st.columns(2)
            with c1:
                fl("Grouping Field")
                st.selectbox("", ["card_id", "account_id", "device_id"], label_visibility="collapsed")
            with c2:
                fl("Time Window (days)")
                st.number_input("", 1, 30, 3, label_visibility="collapsed", key="vel_days")
            fl("Count Threshold")
            st.number_input("", 1, 500, 40, label_visibility="collapsed", key="vel_thresh")

        elif "Amount" in rule_type:
            fl("Amount Threshold (USD)")
            st.number_input("", 1, 100000, 5000, label_visibility="collapsed", key="amt_thresh")

        elif "BIN" in rule_type:
            c1, c2 = st.columns(2)
            with c1:
                fl("Time Window (days)")
                st.number_input("", 1, 30, 1, label_visibility="collapsed", key="bin_days")
            with c2:
                fl("Unique Card Threshold")
                st.number_input("", 1, 200, 20, label_visibility="collapsed", key="bin_thresh")

        st.markdown('</div>', unsafe_allow_html=True)

        # ── 3. Parameters ─────────────────────────────────────────────────────
        st.markdown('<div class="card"><div class="card-title">3 — Parameters</div>', unsafe_allow_html=True)
        fl("Total Transaction Volume")
        volume = st.slider("", 100, 2000, 500, 100, label_visibility="collapsed")

        fl("Fraud Ratio (%)")
        fraud_pct = st.slider("", 5, 50, 20, 5, label_visibility="collapsed")
        fraud_n = int(volume * fraud_pct / 100)
        legit_n = volume - fraud_n
        st.caption(f"{fraud_n:,} fraud  +  {legit_n:,} legitimate transactions")

        fl("Time Window (days)")
        st.slider("", 1, 30, 7, label_visibility="collapsed", key="param_window")

        st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

        fl("Ollama Model")
        st.selectbox("", ["llama3", "mistral", "llama3.1"], label_visibility="collapsed")
        fl("Temperature")
        st.slider("", 0.1, 1.0, 0.7, 0.1, label_visibility="collapsed",
                  help="Higher = more varied patterns. Lower = more consistent.")
        st.markdown('</div>', unsafe_allow_html=True)

        st.button("Run Simulation", use_container_width=True)

    # ── Right: Results ────────────────────────────────────────────────────────
    with col_r:

        st.markdown('<div class="card"><div class="card-title">LLM Fraud Blueprint</div>', unsafe_allow_html=True)
        info("The LLM reads your scenario and returns fraud behavior parameters. Python then generates rows from those parameters.")
        empty("Awaiting Input",
              "After clicking Run, Llama 3 will return a fraud blueprint — amount ranges, velocity, timing, merchant types — shown here.")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="card"><div class="card-title">Dataset Summary</div>', unsafe_allow_html=True)
        d1, d2, d3 = st.columns(3)
        with d1: metric("Total Rows", "—")
        with d2: metric("Fraud Rows", "—", kind="d")
        with d3: metric("Legit Rows", "—", kind="t")
        st.markdown("<br>", unsafe_allow_html=True)
        empty("No Dataset Yet", "The labeled transaction table will appear here after the simulation runs.")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="card"><div class="card-title">Rule Results</div>', unsafe_allow_html=True)
        r1, r2, r3, r4 = st.columns(4)
        with r1: metric("True Positives",  "—")
        with r2: metric("False Positives", "—", kind="d")
        with r3: metric("False Negatives", "—", kind="w")
        with r4: metric("True Negatives",  "—", kind="t")
        st.markdown("<br>", unsafe_allow_html=True)
        empty("Awaiting Simulation",
              "Rule verdict and full transaction table with rule_triggered column will appear here.")
        st.markdown('</div>', unsafe_allow_html=True)

        e1, e2 = st.columns(2)
        with e1: st.button("Download Dataset CSV", use_container_width=True, disabled=True)
        with e2: st.button("Download JSON",        use_container_width=True, disabled=True)
        st.caption("Export enabled after simulation.")


# ══════════════════════════════════════════════════════════════════════════════
# REPORTS AND METRICS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Reports and Metrics":
    st.title("Reports and Metrics")
    st.caption("Performance metrics and visualizations from the rule simulation.")
    st.divider()

    m1, m2, m3, m4, m5 = st.columns(5)
    for col, lbl, sub, kind in [
        (m1, "Precision",           "TP / (TP + FP)",  ""),
        (m2, "Recall",              "TP / (TP + FN)",  "t"),
        (m3, "F1 Score",            "Harmonic mean",   ""),
        (m4, "False Positive Rate", "FP / (FP + TN)",  "w"),
        (m5, "Alert Rate",          "(TP+FP) / Total", "d"),
    ]:
        with col: metric(lbl, "—", sub, kind)

    st.markdown("<br>", unsafe_allow_html=True)

    ch1, ch2 = st.columns(2, gap="large")
    with ch1:
        st.markdown('<div class="card"><div class="card-title">Confusion Matrix Heatmap</div>', unsafe_allow_html=True)
        empty("Chart Pending", "Plotly heatmap of TP, FP, FN, TN — rendered after simulation.")
        st.markdown('</div>', unsafe_allow_html=True)
    with ch2:
        st.markdown('<div class="card"><div class="card-title">Precision / Recall / F1</div>', unsafe_allow_html=True)
        empty("Chart Pending", "Bar chart comparing all three metric scores.")
        st.markdown('</div>', unsafe_allow_html=True)

    ch3, ch4 = st.columns(2, gap="large")
    with ch3:
        st.markdown('<div class="card"><div class="card-title">Fraud vs Legitimate Distribution</div>', unsafe_allow_html=True)
        empty("Chart Pending", "Pie chart of fraud ratio in the generated dataset.")
        st.markdown('</div>', unsafe_allow_html=True)
    with ch4:
        st.markdown('<div class="card"><div class="card-title">Transaction Volume Timeline</div>', unsafe_allow_html=True)
        empty("Chart Pending", "Transaction volume over time with fraud highlighted.")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="card"><div class="card-title">Rule Interpretation</div>', unsafe_allow_html=True)
    info("After simulation, a plain English explanation of rule effectiveness will be generated here.")
    empty("Awaiting Simulation",
          "Example: Your rule caught 78% of fraud but raised false alarms on 32% of legitimate transactions. Consider tightening the threshold from 40 to 25.")
    st.markdown('</div>', unsafe_allow_html=True)

    ex1, ex2, ex3 = st.columns(3)
    with ex1: st.button("Download Dataset CSV",    use_container_width=True, disabled=True)
    with ex2: st.button("Download Metrics Summary", use_container_width=True, disabled=True)
    with ex3: st.button("Export HTML Report",       use_container_width=True, disabled=True)
    st.caption("All export options will be enabled after a simulation is completed.")


