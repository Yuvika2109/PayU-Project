"""
FraudSynth — Dataset Generator UI
──────────────────────────────────
Simple Streamlit interface for the fraud_generator pipeline.
Accepts scenario input → generates blueprint → builds CSV → download.

Run from the fraud_generator/ directory:
    cd fraud_generator
    streamlit run app.py
"""

import sys
import os
import time
import json
import streamlit as st
import pandas as pd
from datetime import datetime

# ── Ensure fraud_generator modules are importable ─────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from agents.scenario_interpreter import ScenarioInterpreterAgent, KNOWN_SCENARIOS
from agents.blueprint_generator import BlueprintGeneratorAgent

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="FraudSynth — Dataset Generator",
    page_icon="🛡️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ══════════════════════════════════════════════════════════════════════════════
# THEME
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&display=swap');
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap');

  :root {
    --dark:   #00383D;
    --green:  #A6C307;
    --teal:   #005159;
    --bg:     #F4F6F0;
    --card:   #FFFFFF;
    --border: #DFE6D8;
    --text:   #1B2E1B;
    --muted:  #6B8A6B;
  }

  html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif !important;
    background: var(--bg) !important;
    color: var(--text);
  }
  #MainMenu, footer, header { visibility: hidden; }
  .block-container { padding: 2rem 2rem !important; max-width: 860px; }

  [data-testid="stSidebar"] { background: var(--dark) !important; }
  [data-testid="stSidebar"] * { color: #fff !important; }

  .stButton > button {
    background: var(--green) !important; color: var(--dark) !important;
    font-weight: 700 !important; border: none !important;
    border-radius: 6px !important; padding: 0.65rem 1.8rem !important;
    font-family: 'DM Sans', sans-serif !important;
    letter-spacing: 0.3px; transition: all 0.15s ease;
  }
  .stButton > button:hover { background: #BBDA0A !important; transform: translateY(-1px); }
  .stButton > button:disabled { background: #D0D8C4 !important; color: #8A9A7A !important; }

  .stSelectbox > div > div, .stTextInput input, .stTextArea textarea, .stNumberInput input {
    border: 1px solid var(--border) !important; border-radius: 6px !important;
    background: #fff !important; font-family: 'DM Sans', sans-serif !important;
  }
  .stTextArea textarea { font-size: 0.92rem !important; }

  hr { border-color: var(--border) !important; }

  .msg-system {
    background: var(--card); border: 1px solid var(--border);
    border-left: 3px solid var(--green); border-radius: 0 8px 8px 0;
    padding: 14px 18px; margin-bottom: 10px; font-size: 0.86rem;
    color: var(--text); line-height: 1.6;
  }
  .msg-step {
    background: #E8F4F5; border: 1px solid #B0D8DC;
    border-left: 3px solid var(--teal); border-radius: 0 8px 8px 0;
    padding: 12px 16px; margin-bottom: 8px; font-size: 0.84rem;
    color: var(--dark); line-height: 1.5;
  }
  .msg-done {
    background: #F0F6E8; border: 1px solid #C8DEB0;
    border-left: 3px solid var(--green); border-radius: 0 8px 8px 0;
    padding: 14px 18px; margin-bottom: 10px; font-size: 0.86rem;
    color: var(--dark); line-height: 1.6;
  }
  .msg-error {
    background: #FFF0F0; border: 1px solid #E8B0B0;
    border-left: 3px solid #D32F2F; border-radius: 0 8px 8px 0;
    padding: 14px 18px; margin-bottom: 10px; font-size: 0.86rem;
    color: #5A1A1A; line-height: 1.6;
  }

  .stat-bar { display: flex; gap: 12px; margin: 10px 0; flex-wrap: wrap; }
  .stat-chip {
    background: var(--card); border: 1px solid var(--border);
    border-radius: 20px; padding: 6px 14px; font-size: 0.76rem;
    font-weight: 600; color: var(--dark);
  }
  .stat-chip .val { color: var(--teal); }

  .bp-preview {
    background: #1B2E1B; color: #A6C307; border-radius: 8px;
    padding: 16px 18px; font-family: 'JetBrains Mono', monospace;
    font-size: 0.78rem; line-height: 1.7; overflow-x: auto;
    margin: 10px 0; max-height: 300px; overflow-y: auto;
  }

  .brand { text-align: center; padding: 20px 0 8px; }
  .brand-title { font-size: 1.6rem; font-weight: 800; color: var(--dark); letter-spacing: -0.5px; }
  .brand-sub { font-size: 0.68rem; color: var(--green); letter-spacing: 1.5px; text-transform: uppercase; margin-top: 2px; }
  .brand-line { width: 60px; height: 3px; background: var(--green); margin: 12px auto 0; border-radius: 2px; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="brand">
  <div class="brand-title">FraudSynth</div>
  <div class="brand-sub">PayU Risk Intelligence — Dataset Generator</div>
  <div class="brand-line"></div>
</div>
""", unsafe_allow_html=True)

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════
for k in ("messages", "df", "blueprint", "params"):
    if k not in st.session_state:
        st.session_state[k] = [] if k == "messages" else None


def add_msg(text, kind="system"):
    st.session_state["messages"].append({"text": text, "kind": kind})


# ══════════════════════════════════════════════════════════════════════════════
# INPUT MODE TABS
# ══════════════════════════════════════════════════════════════════════════════
tab_chat, tab_form = st.tabs(["💬  Describe in Plain English", "📋  Fill a Form"])

with tab_chat:
    st.markdown(
        '<div style="font-size:0.82rem;color:#6B8A6B;margin-bottom:10px;">'
        'Type what you need in your own words. Examples:</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div style="font-size:0.78rem;color:#6B8A6B;line-height:1.8;margin-bottom:14px;">'
        '• "Generate a BIN attack dataset with 50,000 transactions, 5% fraud, CSV"<br>'
        '• "Money laundering data — 10k rows, one-third fraud ratio, parquet"<br>'
        '• "Card testing fraud, 20 thousand transactions, 8 percent fraud, JSON"</div>',
        unsafe_allow_html=True,
    )
    chat_input = st.text_area(
        "Describe your scenario", height=90, key="chat_input",
        placeholder="Describe what you need...",
        label_visibility="collapsed",
    )
    chat_go = st.button("Generate Dataset", key="chat_go", use_container_width=True)

with tab_form:
    st.markdown(
        '<div style="font-size:0.82rem;color:#6B8A6B;margin-bottom:12px;">'
        'Pick your options below:</div>',
        unsafe_allow_html=True,
    )

    scenario_options = [k.title() for k in KNOWN_SCENARIOS.keys()]
    f_scenario = st.selectbox("Fraud Scenario", scenario_options, index=0)

    fc1, fc2 = st.columns(2)
    with fc1:
        f_rows = st.number_input("Total Rows", min_value=1000, max_value=100000,
                                  value=5000, step=1000)
    with fc2:
        f_ratio = st.slider("Fraud Ratio (%)", min_value=1, max_value=50, value=5)

    f_format = st.selectbox("Output Format", ["csv", "json", "parquet"])

    fraud_n = int(f_rows * f_ratio / 100)
    legit_n = f_rows - fraud_n
    st.caption(f"{fraud_n:,} fraud  +  {legit_n:,} legitimate transactions")

    form_go = st.button("Generate Dataset", key="form_go", use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# GENERATION PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

def run_pipeline(user_input: str = None, form_params: dict = None):
    """Run the full generation pipeline and update session state."""

    st.session_state["messages"] = []
    st.session_state["df"] = None
    st.session_state["blueprint"] = None
    st.session_state["params"] = None

    # ── Step 1: Interpret input ───────────────────────────────────────────
    add_msg("⏳ Interpreting your input...", "step")
    interpreter = ScenarioInterpreterAgent()

    if form_params:
        params = {
            "scenario_name": form_params["scenario"],
            "rows": form_params["rows"],
            "fraud_ratio": form_params["ratio"] / 100,
            "output_format": form_params["format"],
        }
        interpreter._fill_defaults(params)
        interpreter._enrich_scenario(params)
    else:
        params = interpreter.interpret(user_input)

    st.session_state["params"] = params

    add_msg(
        f"✅ <b>Interpreted:</b> {params['scenario_name']} &nbsp;|&nbsp; "
        f"{params['rows']:,} rows &nbsp;|&nbsp; "
        f"{params['fraud_ratio']*100:.1f}% fraud &nbsp;|&nbsp; "
        f"{params['output_format'].upper()}",
        "done",
    )

    # ── Step 2: Generate blueprint ────────────────────────────────────────
    add_msg("⏳ Generating fraud blueprint via Llama 3... (30–60 sec)", "step")

    try:
        bp_agent = BlueprintGeneratorAgent()
        blueprint = bp_agent.generate(params)
        st.session_state["blueprint"] = blueprint
        add_msg("✅ Blueprint generated successfully.", "done")
    except Exception as e:
        add_msg(f"❌ Blueprint generation failed: {e}", "error")
        return

    # ── Step 3: Build dataset ─────────────────────────────────────────────
    add_msg("⏳ Building dataset from blueprint...", "step")

    try:
        from core.dataset_engine import DatasetEngine
        engine = DatasetEngine(blueprint)
        df = engine.generate()

        # Sort by timestamp ascending
        if "timestamp" in df.columns:
            df = df.sort_values("timestamp").reset_index(drop=True)

        st.session_state["df"] = df

        fraud_col = "fraud_label" if "fraud_label" in df.columns else "is_fraud"
        fraud_count = int(df[fraud_col].sum()) if fraud_col in df.columns else "?"
        add_msg(
            f"✅ <b>Dataset ready:</b> {len(df):,} rows &nbsp;|&nbsp; "
            f"{fraud_count} fraud transactions",
            "done",
        )

    except Exception as e:
        add_msg(f"❌ Dataset building failed: {e}", "error")
        return


# ── Trigger pipeline ──────────────────────────────────────────────────────────
if chat_go and chat_input.strip():
    with st.spinner(""):
        run_pipeline(user_input=chat_input.strip())

if form_go:
    with st.spinner(""):
        run_pipeline(form_params={
            "scenario": f_scenario,
            "rows": f_rows,
            "ratio": f_ratio,
            "format": f_format,
        })


# ══════════════════════════════════════════════════════════════════════════════
# RESULTS
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state["messages"]:
    st.divider()
    st.markdown(
        '<div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;'
        'letter-spacing:0.9px;color:#00383D;margin-bottom:10px;">Pipeline Log</div>',
        unsafe_allow_html=True,
    )

    for msg in st.session_state["messages"]:
        css_class = f"msg-{msg['kind']}"
        st.markdown(f'<div class="{css_class}">{msg["text"]}</div>', unsafe_allow_html=True)


# ── Blueprint preview ─────────────────────────────────────────────────────────
if st.session_state["blueprint"]:
    with st.expander("🔍 View Blueprint", expanded=False):
        bp = st.session_state["blueprint"]
        bp_json = json.dumps(bp, indent=2, default=str)
        st.markdown(f'<div class="bp-preview">{bp_json[:3000]}</div>', unsafe_allow_html=True)

        bp_bytes = json.dumps(bp, indent=2, default=str).encode("utf-8")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button(
            "Download Blueprint JSON",
            bp_bytes,
            f"blueprint_{ts}.json",
            "application/json",
            use_container_width=True,
        )


# ── Dataset preview + download ────────────────────────────────────────────────
if st.session_state["df"] is not None:
    df = st.session_state["df"]
    params = st.session_state["params"]

    st.markdown(
        '<div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;'
        'letter-spacing:0.9px;color:#00383D;margin:18px 0 10px;">Dataset Preview</div>',
        unsafe_allow_html=True,
    )

    fraud_col = "fraud_label" if "fraud_label" in df.columns else "is_fraud"
    if fraud_col in df.columns:
        fraud_n = int(df[fraud_col].sum())
        legit_n = len(df) - fraud_n
    else:
        fraud_n = "?"
        legit_n = "?"

    st.markdown(
        f'<div class="stat-bar">'
        f'<div class="stat-chip">Total: <span class="val">{len(df):,}</span></div>'
        f'<div class="stat-chip">Fraud: <span class="val">{fraud_n:,}</span></div>'
        f'<div class="stat-chip">Legit: <span class="val">{legit_n:,}</span></div>'
        f'<div class="stat-chip">Columns: <span class="val">{len(df.columns)}</span></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.dataframe(df.head(100), use_container_width=True, height=300)

    if len(df) > 100:
        st.caption(f"Showing first 100 of {len(df):,} rows.")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    d1, d2 = st.columns(2)
    with d1:
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇ Download CSV",
            csv_bytes,
            f"enterprise_fraud_{ts}.csv",
            "text/csv",
            use_container_width=True,
        )
    with d2:
        json_bytes = df.to_json(orient="records", indent=2).encode("utf-8")
        st.download_button(
            "⬇ Download JSON",
            json_bytes,
            f"enterprise_fraud_{ts}.json",
            "application/json",
            use_container_width=True,
        )

elif not st.session_state["messages"]:
    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    st.markdown(
        '<div style="background:#F8FAF4;border:1.5px dashed #DFE6D8;border-radius:8px;'
        'padding:30px 20px;text-align:center;">'
        '<div style="font-size:0.9rem;font-weight:600;color:#00383D;margin-bottom:6px;">'
        'Ready to Generate</div>'
        '<div style="font-size:0.8rem;color:#6B8A6B;line-height:1.7;">'
        'Describe a fraud scenario above or fill in the form.<br>'
        'The system will generate a blueprint via Llama 3 and build your dataset.</div>'
        '</div>',
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# FOOTER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div style='height:30px'></div>", unsafe_allow_html=True)
st.markdown(
    '<div style="text-align:center;font-size:0.68rem;color:#6B8A6B;">'
    'FraudSynth v0.2 &nbsp;·&nbsp; PayU Risk Intelligence &nbsp;·&nbsp; '
    'Powered by Llama 3 + Faker + NumPy</div>',
    unsafe_allow_html=True,
)