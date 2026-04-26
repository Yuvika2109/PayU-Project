import sys
import os
import streamlit as st
import pandas as pd

# ── Path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "generator"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "rule_engine"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "reporting"))

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="FraudSynth — PayU",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ══════════════════════════════════════════════════════════════════════════════
# THEME / CSS
# ══════════════════════════════════════════════════════════════════════════════
THEME = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700&display=swap');

  /* ── palette ──────────────────────────────────────────────────────────── */
  :root {
    --payu-dark:   #00383D;
    --payu-green:  #A6C307;
    --payu-teal:   #005159;
    --bg:          #F4F6F0;
    --card:        #FFFFFF;
    --border:      #DFE6D8;
    --text:        #1B2E1B;
    --muted:       #6B8A6B;
    --red:         #D32F2F;
    --orange:      #EF6C00;
    --green-soft:  #E9F0D0;
  }

  /* ── base ─────────────────────────────────────────────────────────────── */
  html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif !important;
    background: var(--bg) !important;
    color: var(--text);
  }
  #MainMenu, footer, header { visibility: hidden; }
  .block-container { padding: 1.8rem 2.4rem !important; }

  /* ── sidebar ──────────────────────────────────────────────────────────── */
  [data-testid="stSidebar"] {
    background: var(--payu-dark) !important;
    border-right: 3px solid var(--payu-green);
  }
  [data-testid="stSidebar"] * { color: #fff !important; }
  [data-testid="stSidebar"] .stRadio label {
    font-size: 0.84rem !important;
    padding: 6px 0 !important;
  }

  /* ── buttons ──────────────────────────────────────────────────────────── */
  .stButton > button {
    background: var(--payu-green) !important;
    color: var(--payu-dark) !important;
    font-weight: 700 !important;
    border: none !important;
    border-radius: 6px !important;
    padding: 0.6rem 1.5rem !important;
    letter-spacing: 0.3px;
    transition: background 0.15s ease;
  }
  .stButton > button:hover { background: #BBDA0A !important; }
  .stButton > button:disabled {
    background: #D0D8C4 !important;
    color: #8A9A7A !important;
  }

  /* ── inputs ───────────────────────────────────────────────────────────── */
  .stSelectbox > div > div,
  .stTextInput input,
  .stTextArea textarea,
  .stNumberInput input {
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
    background: #fff !important;
    font-family: 'DM Sans', sans-serif !important;
  }

  /* ── dividers ─────────────────────────────────────────────────────────── */
  hr { border-color: var(--border) !important; }

  /* ── dataframe tweaks ─────────────────────────────────────────────────── */
  .stDataFrame { border-radius: 6px; overflow: hidden; }
</style>
"""
st.markdown(THEME, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# REUSABLE COMPONENTS
# ══════════════════════════════════════════════════════════════════════════════

def card_start(title: str):
    """Open a styled card with a title bar."""
    st.markdown(
        f"""<div style="background:var(--card);border:1px solid var(--border);
        border-radius:8px;padding:20px 22px;margin-bottom:14px;">
        <div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;
        letter-spacing:0.9px;color:var(--payu-dark);border-bottom:2px solid var(--payu-green);
        padding-bottom:7px;margin-bottom:14px;display:inline-block;">{title}</div>""",
        unsafe_allow_html=True,
    )

def card_end():
    st.markdown("</div>", unsafe_allow_html=True)

def kpi(label, value, subtitle="", accent="green"):
    """Render a KPI metric block. accent: green | teal | orange | red"""
    colors = {
        "green":  "var(--payu-green)",
        "teal":   "var(--payu-teal)",
        "orange": "var(--orange)",
        "red":    "var(--red)",
    }
    border = colors.get(accent, colors["green"])
    st.markdown(
        f"""<div style="background:var(--card);border:1px solid var(--border);
        border-left:4px solid {border};border-radius:6px;padding:13px 16px;">
        <div style="font-size:0.66rem;font-weight:700;text-transform:uppercase;
        letter-spacing:0.8px;color:var(--muted);margin-bottom:3px;">{label}</div>
        <div style="font-size:1.6rem;font-weight:700;color:var(--payu-dark);
        line-height:1.15;">{value}</div>
        <div style="font-size:0.7rem;color:var(--muted);margin-top:3px;">{subtitle}</div>
        </div>""",
        unsafe_allow_html=True,
    )

def empty_state(title, desc):
    st.markdown(
        f"""<div style="background:#F8FAF4;border:1.5px dashed var(--border);
        border-radius:6px;padding:28px 18px;text-align:center;">
        <div style="font-size:0.88rem;font-weight:600;color:var(--payu-dark);
        margin-bottom:5px;">{title}</div>
        <div style="font-size:0.78rem;color:var(--muted);line-height:1.6;">{desc}</div>
        </div>""",
        unsafe_allow_html=True,
    )

def info_box(text):
    st.markdown(
        f"""<div style="background:#E6F1F2;border-left:3px solid var(--payu-teal);
        padding:9px 13px;border-radius:0 5px 5px 0;font-size:0.8rem;
        color:var(--payu-dark);margin-bottom:10px;">{text}</div>""",
        unsafe_allow_html=True,
    )

def field_label(text):
    st.markdown(
        f"""<div style="font-size:0.68rem;font-weight:700;text-transform:uppercase;
        letter-spacing:0.7px;color:var(--muted);margin:12px 0 3px;">{text}</div>""",
        unsafe_allow_html=True,
    )

def step_card(num, title, desc):
    st.markdown(
        f"""<div style="background:#F8FAF4;border-radius:6px;padding:14px 16px;
        border-top:2px solid var(--payu-green);height:100%;">
        <div style="font-size:0.6rem;font-weight:700;color:var(--payu-green);
        letter-spacing:1.5px;margin-bottom:5px;">STEP {num}</div>
        <div style="font-weight:600;font-size:0.84rem;color:var(--payu-dark);
        margin-bottom:5px;">{title}</div>
        <div style="font-size:0.76rem;color:var(--muted);line-height:1.55;">{desc}</div>
        </div>""",
        unsafe_allow_html=True,
    )

def verdict_box(text):
    st.markdown(
        f"""<div style="background:#F0F6F0;border:1px solid #C6DEC6;
        border-radius:6px;padding:12px 16px;font-size:0.82rem;
        color:var(--payu-dark);line-height:1.7;margin-bottom:8px;">{text}</div>""",
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════
for key in ("df", "metrics", "sim_done"):
    if key not in st.session_state:
        st.session_state[key] = None
if st.session_state["sim_done"] is None:
    st.session_state["sim_done"] = False


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    # Branding header
    st.markdown(
        """
        <div style="padding:22px 0 18px;text-align:center;">
            <div style="font-size:1.25rem;font-weight:800;color:#fff;
            letter-spacing:-0.4px;">FraudSynth</div>
            <div style="font-size:0.62rem;color:#A6C307;letter-spacing:1.4px;
            text-transform:uppercase;margin-top:2px;">PayU Risk Intelligence</div>
        </div>
        <hr style="border-color:rgba(166,195,7,0.2);margin:0 0 14px;">
        <div style="font-size:0.6rem;text-transform:uppercase;letter-spacing:1px;
        color:#7AADAD;margin-bottom:6px;">Navigation</div>
        """,
        unsafe_allow_html=True,
    )

    page = st.radio(
        "",
        ["Dashboard", "Simulate", "Reports & Metrics", "About"],
        label_visibility="collapsed",
    )

    # ── system status ─────────────────────────────────────────────────────────
    ds_ready = st.session_state["df"] is not None
    ds_label = "Generated" if ds_ready else "Not generated"
    ds_color = "#A6C307" if ds_ready else "#F57C00"

    st.markdown(
        f"""
        <hr style="border-color:rgba(166,195,7,0.2);margin:14px 0;">
        <div style="font-size:0.6rem;text-transform:uppercase;letter-spacing:1px;
        color:#7AADAD;margin-bottom:8px;">System Status</div>
        <div style="font-size:0.76rem;color:#C8E8C8;line-height:2.1;">
            <span style="color:#A6C307;font-weight:700;">&#9679;</span>&ensp;Ollama — Ready<br>
            <span style="color:#A6C307;font-weight:700;">&#9679;</span>&ensp;Llama 3 — Ready<br>
            <span style="color:{ds_color};font-weight:700;">&#9679;</span>&ensp;Dataset — {ds_label}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE: DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
if page == "Dashboard":
    st.markdown(
        '<div style="font-size:1.5rem;font-weight:700;color:var(--payu-dark);">Dashboard</div>'
        '<div style="font-size:0.82rem;color:var(--muted);margin-bottom:6px;">'
        'Overview of dataset generation and rule simulation activity.</div>',
        unsafe_allow_html=True,
    )
    st.divider()

    df = st.session_state["df"]
    met = st.session_state["metrics"]

    # ── KPI row ───────────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        kpi("Datasets Generated",
            "1" if df is not None else "—",
            "Ready" if df is not None else "No runs yet")
    with k2:
        kpi("Rules Simulated",
            "1" if met is not None else "—",
            "Done" if met is not None else "No runs yet", "teal")
    with k3:
        kpi("Precision",
            f"{met['precision']:.0%}" if met else "—",
            "TP / (TP + FP)" if met else "Run a simulation first", "orange")
    with k4:
        kpi("Recall",
            f"{met['recall']:.0%}" if met else "—",
            "TP / (TP + FN)" if met else "Run a simulation first", "red")

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # ── Activity + Examples ───────────────────────────────────────────────────
    col_l, col_r = st.columns([3, 2], gap="large")

    with col_l:
        card_start("Recent Activity")
        if df is not None and met is not None:
            st.markdown(
                f"""<div style="padding:8px 0;font-size:0.84rem;border-bottom:1px solid #EEF2EE;">
                <span style="font-weight:600;color:var(--payu-dark);">Last simulation complete</span>
                <span style="color:var(--muted);margin-left:8px;">{len(df):,} rows &nbsp;|&nbsp;
                {int(df['is_fraud'].sum())} fraud &nbsp;|&nbsp;
                Precision {met['precision']:.0%} &nbsp;|&nbsp; Recall {met['recall']:.0%}</span>
                </div>""",
                unsafe_allow_html=True,
            )
        else:
            empty_state(
                "No Simulations Yet",
                "Go to <b>Simulate</b>, describe a fraud scenario, enter a detection rule, set parameters, and click <b>Run</b>.",
            )
        card_end()

    with col_r:
        card_start("Example Scenarios")
        scenarios = [
            ("BIN Attack", "Multiple cards with same BIN tested rapidly"),
            ("Account Takeover", "Unauthorized access, unusual spend pattern"),
            ("Card Testing", "Small amounts to verify card validity"),
            ("Velocity Abuse", "Same card used excessively at one merchant"),
        ]
        for name, desc in scenarios:
            st.markdown(
                f"""<div style="padding:7px 0;border-bottom:1px solid #EEF2EE;">
                <span style="font-weight:600;font-size:0.83rem;color:var(--payu-dark);">{name}</span>
                <span style="font-size:0.76rem;color:var(--muted);margin-left:6px;">{desc}</span>
                </div>""",
                unsafe_allow_html=True,
            )
        st.markdown(
            '<div style="font-size:0.72rem;color:var(--muted);margin-top:8px;font-style:italic;">'
            "Any fraud scenario can be described in plain text.</div>",
            unsafe_allow_html=True,
        )
        card_end()

    # ── How-to-use steps ──────────────────────────────────────────────────────
    card_start("How To Use")
    s1, s2, s3 = st.columns(3)
    with s1:
        step_card("01", "Describe, Configure & Run",
                  "Go to Simulate. Type any fraud scenario, enter your detection rule, set volume and fraud ratio.")
    with s2:
        step_card("02", "Dataset + Rule Applied",
                  "The system generates a labeled dataset and immediately applies your rule to every row.")
    with s3:
        step_card("03", "Review Metrics",
                  "Go to Reports & Metrics to see Precision, Recall, F1, and the full confusion matrix.")
    card_end()


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE: SIMULATE
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Simulate":
    st.markdown(
        '<div style="font-size:1.5rem;font-weight:700;color:var(--payu-dark);">Simulate</div>'
        '<div style="font-size:0.82rem;color:var(--muted);margin-bottom:6px;">'
        "Describe a fraud scenario, enter a detection rule, configure parameters — then run everything together.</div>",
        unsafe_allow_html=True,
    )
    st.divider()

    col_left, col_right = st.columns([2, 3], gap="large")

    # ── LEFT: Input panel ─────────────────────────────────────────────────────
    with col_left:

        # 1 — Scenario
        card_start("1 — Fraud Scenario")
        field_label("Describe the fraud scenario")
        scenario_input = st.text_area(
            "", height=90, label_visibility="collapsed", key="scenario_input",
            placeholder="e.g. BIN attack where fraudsters rapidly test multiple cards sharing the same BIN prefix with small transaction amounts...",
        )
        st.markdown(
            '<div style="font-size:0.71rem;color:var(--muted);margin-top:3px;">'
            "Examples: BIN Attack &nbsp;|&nbsp; Account Takeover &nbsp;|&nbsp; "
            "Card Testing &nbsp;|&nbsp; Velocity Abuse</div>",
            unsafe_allow_html=True,
        )
        card_end()

        # 2 — Detection Rule
        card_start("2 — Detection Rule")
        field_label("Rule condition")
        rule_text = st.text_area(
            "", height=68, label_visibility="collapsed", key="rule_input",
            placeholder="e.g. number_of_transactions(card_id, last_3_days) > 40",
        )
        info_box(
            "The rule will be evaluated against every transaction. "
            "A <b>rule_triggered</b> column (True / False) will be added."
        )

        field_label("Rule Type")
        rule_type_raw = st.selectbox(
            "", [
                "Velocity — Transaction count by card in time window",
                "Amount  — Single transaction exceeds threshold",
                "BIN     — Unique cards on same BIN in time window",
            ],
            label_visibility="collapsed",
        )

        # Derive clean rule type key
        if "Velocity" in rule_type_raw:
            rule_type = "velocity"
        elif "Amount" in rule_type_raw:
            rule_type = "amount"
        else:
            rule_type = "bin"

        # Dynamic parameter widgets per rule type
        rule_params: dict = {}

        if rule_type == "velocity":
            rc1, rc2 = st.columns(2)
            with rc1:
                field_label("Grouping Field")
                rule_params["group_by"] = st.selectbox(
                    "", ["card_id", "account_id", "device_id"],
                    label_visibility="collapsed",
                )
            with rc2:
                field_label("Time Window (days)")
                rule_params["window_days"] = st.number_input(
                    "", 1, 30, 3, label_visibility="collapsed", key="vel_days",
                )
            field_label("Count Threshold")
            rule_params["threshold"] = st.number_input(
                "", 1, 500, 40, label_visibility="collapsed", key="vel_thresh",
            )

        elif rule_type == "amount":
            field_label("Amount Threshold (USD)")
            rule_params["threshold"] = st.number_input(
                "", 1, 100_000, 5000, label_visibility="collapsed", key="amt_thresh",
            )

        elif rule_type == "bin":
            rb1, rb2 = st.columns(2)
            with rb1:
                field_label("Time Window (days)")
                rule_params["window_days"] = st.number_input(
                    "", 1, 30, 1, label_visibility="collapsed", key="bin_days",
                )
            with rb2:
                field_label("Unique Card Threshold")
                rule_params["threshold"] = st.number_input(
                    "", 1, 200, 20, label_visibility="collapsed", key="bin_thresh",
                )
        card_end()

        # 3 — Parameters
        card_start("3 — Parameters")
        field_label("Total Transaction Volume")
        volume = st.slider("", 100, 2000, 500, 100, label_visibility="collapsed")

        field_label("Fraud Ratio (%)")
        fraud_pct = st.slider("", 5, 50, 20, 5, label_visibility="collapsed")

        fraud_n = int(volume * fraud_pct / 100)
        legit_n = volume - fraud_n
        st.caption(f"{fraud_n:,} fraud  +  {legit_n:,} legitimate transactions")

        st.markdown('<hr style="border-color:var(--border);margin:14px 0;">', unsafe_allow_html=True)

        field_label("Ollama Model")
        model = st.selectbox("", ["llama3", "mistral", "llama3.1"], label_visibility="collapsed")

        field_label("Temperature")
        temperature = st.slider("", 0.1, 1.0, 0.7, 0.1, label_visibility="collapsed")
        card_end()

        # ── Run button ────────────────────────────────────────────────────────
        run_clicked = st.button("Run Simulation", use_container_width=True)

    # ── RIGHT: Results panel ──────────────────────────────────────────────────
    with col_right:

        # --- placeholder: wire actual generation here later ---
        if run_clicked:
            if not scenario_input.strip():
                st.error("Please describe a fraud scenario before running.")
            else:
                st.info("Generation pipeline not wired yet — this is the base UI.")

        df = st.session_state["df"]
        met = st.session_state["metrics"]

        # Dataset summary card
        card_start("Dataset Summary")
        d1, d2, d3 = st.columns(3)
        if df is not None:
            with d1: kpi("Total Rows", f"{len(df):,}")
            with d2: kpi("Fraud Rows", str(int(df["is_fraud"].sum())), accent="red")
            with d3: kpi("Legit Rows", str(int((~df["is_fraud"]).sum())), accent="teal")
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            st.dataframe(df, use_container_width=True, height=250)
        else:
            with d1: kpi("Total Rows", "—")
            with d2: kpi("Fraud Rows", "—", accent="red")
            with d3: kpi("Legit Rows", "—", accent="teal")
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            empty_state("No Dataset Yet",
                        "The labeled transaction table will appear here after the simulation runs.")
        card_end()

        # Rule results card
        card_start("Rule Results")
        r1, r2, r3, r4 = st.columns(4)
        if met is not None:
            with r1: kpi("True Positives", str(met["tp"]))
            with r2: kpi("False Positives", str(met["fp"]), accent="red")
            with r3: kpi("False Negatives", str(met["fn"]), accent="orange")
            with r4: kpi("True Negatives", str(met["tn"]), accent="teal")
            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
            for v in met.get("verdicts", {}).values():
                verdict_box(v)
        else:
            with r1: kpi("True Positives", "—")
            with r2: kpi("False Positives", "—", accent="red")
            with r3: kpi("False Negatives", "—", accent="orange")
            with r4: kpi("True Negatives", "—", accent="teal")
            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
            empty_state("Awaiting Simulation",
                        "Rule results and verdict will appear here after running.")
        card_end()

        # Export buttons
        if df is not None:
            e1, e2 = st.columns(2)
            with e1:
                csv = df.to_csv(index=False).encode("utf-8")
                st.download_button("Download Dataset CSV", csv, "fraudsynth_dataset.csv",
                                   "text/csv", use_container_width=True)
            with e2:
                json_bytes = df.to_json(orient="records", indent=2).encode("utf-8")
                st.download_button("Download JSON", json_bytes, "fraudsynth_dataset.json",
                                   "application/json", use_container_width=True)
        else:
            e1, e2 = st.columns(2)
            with e1: st.button("Download Dataset CSV", use_container_width=True, disabled=True)
            with e2: st.button("Download JSON", use_container_width=True, disabled=True)
            st.caption("Export enabled after simulation.")


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE: REPORTS & METRICS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Reports & Metrics":
    st.markdown(
        '<div style="font-size:1.5rem;font-weight:700;color:var(--payu-dark);">Reports &amp; Metrics</div>'
        '<div style="font-size:0.82rem;color:var(--muted);margin-bottom:6px;">'
        "Performance metrics and visualizations from the rule simulation.</div>",
        unsafe_allow_html=True,
    )
    st.divider()

    df = st.session_state["df"]
    met = st.session_state["metrics"]

    # ── KPI row ───────────────────────────────────────────────────────────────
    m1, m2, m3, m4, m5 = st.columns(5)
    if met:
        with m1: kpi("Precision",           f"{met['precision']:.0%}",           "TP / (TP + FP)")
        with m2: kpi("Recall",              f"{met['recall']:.0%}",              "TP / (TP + FN)",   "teal")
        with m3: kpi("F1 Score",            f"{met['f1']:.0%}",                  "Harmonic mean")
        with m4: kpi("False Positive Rate", f"{met['false_positive_rate']:.0%}", "FP / (FP + TN)",   "orange")
        with m5: kpi("Alert Rate",          f"{met['alert_rate']:.0%}",          "(TP+FP) / Total",  "red")
    else:
        labels = [
            ("Precision", "TP / (TP + FP)", "green"),
            ("Recall", "TP / (TP + FN)", "teal"),
            ("F1 Score", "Harmonic mean", "green"),
            ("False Positive Rate", "FP / (FP + TN)", "orange"),
            ("Alert Rate", "(TP+FP) / Total", "red"),
        ]
        for col, (lbl, sub, acc) in zip([m1, m2, m3, m4, m5], labels):
            with col:
                kpi(lbl, "—", sub, acc)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # ── Charts ────────────────────────────────────────────────────────────────
    if df is not None and met is not None:
        # --- placeholder: replace with real Plotly charts when wired ---
        ch1, ch2 = st.columns(2, gap="large")
        with ch1:
            card_start("Confusion Matrix Heatmap")
            st.info("Plotly chart will render here.")
            card_end()
        with ch2:
            card_start("Precision / Recall / F1")
            st.info("Plotly chart will render here.")
            card_end()

        ch3, ch4 = st.columns(2, gap="large")
        with ch3:
            card_start("Fraud vs Legitimate Distribution")
            st.info("Plotly chart will render here.")
            card_end()
        with ch4:
            card_start("Transaction Volume Timeline")
            st.info("Plotly chart will render here.")
            card_end()

        # Verdicts
        card_start("Rule Interpretation")
        for v in met.get("verdicts", {}).values():
            verdict_box(v)
        card_end()

        # Exports
        ex1, ex2, ex3 = st.columns(3)
        with ex1:
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("Download Dataset CSV", csv, "fraudsynth_dataset.csv",
                               "text/csv", use_container_width=True)
        with ex2:
            import json as _json
            metrics_export = {k: v for k, v in met.items() if k != "verdicts"}
            st.download_button("Download Metrics Summary",
                               _json.dumps(metrics_export, indent=2).encode("utf-8"),
                               "fraudsynth_metrics.json", "application/json",
                               use_container_width=True)
        with ex3:
            st.button("Export HTML Report", use_container_width=True, disabled=True)
            st.caption("Coming in next sprint.")
    else:
        # ── Empty / placeholder state ─────────────────────────────────────────
        ch1, ch2 = st.columns(2, gap="large")
        with ch1:
            card_start("Confusion Matrix Heatmap")
            empty_state("Chart Pending", "Rendered after simulation.")
            card_end()
        with ch2:
            card_start("Precision / Recall / F1")
            empty_state("Chart Pending", "Bar chart after simulation.")
            card_end()

        ch3, ch4 = st.columns(2, gap="large")
        with ch3:
            card_start("Fraud vs Legitimate Distribution")
            empty_state("Chart Pending", "Pie chart after simulation.")
            card_end()
        with ch4:
            card_start("Transaction Volume Timeline")
            empty_state("Chart Pending", "Timeline after simulation.")
            card_end()

        card_start("Rule Interpretation")
        info_box("After simulation, a plain-English explanation of rule effectiveness will appear here.")
        empty_state("Awaiting Simulation", "Run a simulation from the Simulate page first.")
        card_end()

        ex1, ex2, ex3 = st.columns(3)
        with ex1: st.button("Download Dataset CSV",     use_container_width=True, disabled=True)
        with ex2: st.button("Download Metrics Summary",  use_container_width=True, disabled=True)
        with ex3: st.button("Export HTML Report",        use_container_width=True, disabled=True)
        st.caption("All exports enabled after a simulation is completed.")


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE: ABOUT
# ══════════════════════════════════════════════════════════════════════════════
elif page == "About":
    st.markdown(
        '<div style="font-size:1.5rem;font-weight:700;color:var(--payu-dark);">About FraudSynth</div>'
        '<div style="font-size:0.82rem;color:var(--muted);margin-bottom:6px;">'
        "GenAI-powered synthetic fraud data generation and rule simulation — PayU Risk Intelligence.</div>",
        unsafe_allow_html=True,
    )
    st.divider()

    a_left, a_right = st.columns([3, 2], gap="large")

    with a_left:
        card_start("What Is This?")
        st.markdown(
            """<p style="font-size:0.85rem;line-height:1.75;color:var(--text);margin-bottom:8px;">
            <b>FraudSynth</b> lets you describe any fraud scenario in plain text, provide a detection rule,
            and set dataset parameters — all in one place. Llama&nbsp;3 generates a fraud behavior blueprint.
            Python builds thousands of labeled transactions from that blueprint and immediately applies
            your rule to evaluate its effectiveness.</p>
            <p style="font-size:0.85rem;line-height:1.75;color:var(--text);">
            All without using any real customer data.</p>""",
            unsafe_allow_html=True,
        )
        card_end()

        card_start("System Flow")
        flow = [
            ("01", "User Provides All Inputs",
             "Fraud scenario (free text), detection rule, volume, fraud ratio — all at once."),
            ("02", "LLM Blueprint",
             "Llama 3 returns fraud behavior parameters — amounts, velocity, timing, merchants."),
            ("03", "Dataset Build",
             "Python, Faker, and NumPy generate labeled transaction rows from the blueprint."),
            ("04", "Rule Applied",
             "The rule is evaluated against every row. rule_triggered column added."),
            ("05", "Metrics Report",
             "Scikit-learn computes Precision, Recall, F1, and Confusion Matrix."),
        ]
        for num, title, desc in flow:
            st.markdown(
                f"""<div style="display:flex;gap:12px;padding:9px 0;border-bottom:1px solid #EEF2EE;">
                <div style="font-size:0.62rem;font-weight:700;color:var(--payu-green);
                letter-spacing:1px;min-width:20px;padding-top:2px;">{num}</div>
                <div>
                  <div style="font-weight:600;font-size:0.83rem;color:var(--payu-dark);">{title}</div>
                  <div style="font-size:0.77rem;color:var(--muted);margin-top:2px;line-height:1.5;">{desc}</div>
                </div></div>""",
                unsafe_allow_html=True,
            )
        card_end()

    with a_right:
        card_start("Technology Stack")
        stack = [
            ("Streamlit",         "UI Layer"),
            ("Ollama + Llama 3",  "LLM Engine"),
            ("Faker + NumPy",     "Data Generation"),
            ("Pandas",            "Data Processing"),
            ("Python",            "Rule Engine"),
            ("Scikit-learn",      "Metrics"),
            ("Plotly",            "Visualization"),
        ]
        for name, role in stack:
            st.markdown(
                f"""<div style="display:flex;justify-content:space-between;padding:7px 0;
                border-bottom:1px solid #EEF2EE;font-size:0.8rem;">
                <span style="font-weight:600;color:var(--payu-dark);">{name}</span>
                <span style="color:var(--muted);">{role}</span></div>""",
                unsafe_allow_html=True,
            )
        card_end()

        card_start("Development Team")
        team = [
            ("Student 1", "LLM + Data Generation"),
            ("Student 2", "Rule Engine"),
            ("Student 3", "Metrics + Reporting"),
            ("Student 4", "UI + Integration"),
        ]
        for name, role in team:
            st.markdown(
                f"""<div style="display:flex;justify-content:space-between;align-items:center;
                padding:7px 0;border-bottom:1px solid #EEF2EE;font-size:0.8rem;">
                <span style="font-weight:600;color:var(--payu-dark);">{name}</span>
                <span style="display:inline-block;background:#E6F1F2;color:var(--payu-teal);
                font-size:0.68rem;font-weight:600;padding:2px 8px;border-radius:20px;
                border:1px solid #AEDAE0;">{role}</span></div>""",
                unsafe_allow_html=True,
            )
        card_end()

        card_start("Version")
        st.markdown(
            """<div style="font-size:0.8rem;color:var(--muted);line-height:2.1;">
            <div><b style="color:var(--payu-dark);">Version</b>&ensp;0.2 — Fully Wired</div>
            <div><b style="color:var(--payu-dark);">Sprint</b>&ensp;2 of 4</div>
            <div><b style="color:var(--payu-dark);">Status</b>&ensp;
            <span style="display:inline-block;background:#E6F1F2;color:var(--payu-teal);
            font-size:0.68rem;font-weight:600;padding:2px 8px;border-radius:20px;
            border:1px solid #AEDAE0;">Active Development</span></div>
            <div style="margin-top:6px;padding-top:6px;border-top:1px solid #EEF2EE;">
            <b style="color:var(--payu-dark);">Next</b>&ensp;Time-window rule logic + HTML export</div>
            </div>""",
            unsafe_allow_html=True,
        )
        card_end()
