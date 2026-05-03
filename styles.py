import streamlit as st


def inject():
    st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&family=Lora:ital,wght@0,400;0,500;1,400&display=swap" rel="stylesheet">

<style>
/* ── Base ──────────────────────────────────────────────────────── */
.stApp { background-color: #141413; }

/* Kill Streamlit's default top padding so the header sits near the top */
.stMainBlockContainer,
[data-testid="stMainBlockContainer"],
.block-container,
[data-testid="block-container"] {
    padding-top: 1rem !important;
    padding-bottom: 2rem !important;
}

h1, h2, h3, h4, h5 {
    font-family: 'Poppins', sans-serif !important;
    color: #faf9f5 !important;
    letter-spacing: -0.02em;
}

p, li, .stMarkdown p, .stMarkdown li {
    font-family: 'Lora', serif !important;
    line-height: 1.75;
    color: #e8e6dc;
}

/* ── Hide default header decorations ──────────────────────────── */
[data-testid="stHeader"] { background: transparent; }
footer { display: none; }
#MainMenu { display: none; }

/* ── App header ───────────────────────────────────────────────── */
.irac-header {
    padding: 0.25rem 0 1rem 0;
    border-bottom: 1px solid #2a2925;
    margin-bottom: 1.25rem;
    animation: fadeIn 0.5s ease;
}
.irac-logo {
    font-family: 'Poppins', sans-serif;
    font-size: 2rem;
    font-weight: 700;
    color: #faf9f5;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}
.irac-logo-accent { color: #d97757; }
.irac-tagline {
    font-family: 'Lora', serif;
    font-style: italic;
    color: #b0aea5;
    font-size: 0.9rem;
    margin-top: 0.25rem;
}

/* ── Tabs ─────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    background-color: #1e1d1b !important;
    border-radius: 10px !important;
    padding: 4px !important;
    gap: 2px !important;
    border: 1px solid #2a2925 !important;
}
.stTabs [data-baseweb="tab"] {
    background-color: transparent !important;
    border-radius: 7px !important;
    color: #b0aea5 !important;
    font-family: 'Poppins', sans-serif !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    padding: 8px 18px !important;
    transition: all 0.2s ease !important;
    border: none !important;
}
.stTabs [data-baseweb="tab"]:hover { color: #faf9f5 !important; }
.stTabs [aria-selected="true"] {
    background-color: #d97757 !important;
    color: #141413 !important;
    font-weight: 600 !important;
}

/* ── Buttons ──────────────────────────────────────────────────── */
.stButton > button {
    font-family: 'Poppins', sans-serif !important;
    font-weight: 500 !important;
    border-radius: 8px !important;
    transition: all 0.2s ease !important;
    border: 1px solid #3a3830 !important;
}
.stButton > button[kind="primary"] {
    background: #d97757 !important;
    color: #141413 !important;
    border: none !important;
    font-weight: 600 !important;
}
.stButton > button[kind="primary"]:hover {
    background: #c4633f !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 16px rgba(217, 119, 87, 0.35) !important;
}
.stButton > button:not([kind="primary"]):hover {
    border-color: #d97757 !important;
    color: #d97757 !important;
    transform: translateY(-1px) !important;
}

/* ── Text areas ───────────────────────────────────────────────── */
.stTextArea > div > div > textarea {
    background-color: #1e1d1b !important;
    border: 1px solid #3a3830 !important;
    color: #faf9f5 !important;
    border-radius: 10px !important;
    font-family: 'Lora', serif !important;
    font-size: 15px !important;
    line-height: 1.7 !important;
    padding: 14px !important;
    transition: border-color 0.2s, box-shadow 0.2s !important;
}
.stTextArea > div > div > textarea:focus {
    border-color: #d97757 !important;
    box-shadow: 0 0 0 2px rgba(217, 119, 87, 0.15) !important;
}
.stTextArea label {
    font-family: 'Poppins', sans-serif !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    color: #b0aea5 !important;
}

/* ── Popover (used for Area-of-Law chip) ──────────────────────── */
[data-testid="stPopover"] button {
    background-color: #1e1d1b !important;
    border: 1px solid #3a3830 !important;
    color: #b0aea5 !important;
    font-family: 'Poppins', sans-serif !important;
    font-size: 12px !important;
    font-weight: 500 !important;
    padding: 6px 14px !important;
    border-radius: 999px !important;
    transition: border-color 0.2s, color 0.2s !important;
    width: auto !important;
}
[data-testid="stPopover"] button:hover {
    border-color: #d97757 !important;
    color: #faf9f5 !important;
    transform: none !important;
}

/* ── Selectbox ────────────────────────────────────────────────── */
[data-testid="stSelectbox"] > div > div {
    background-color: #1e1d1b !important;
    border: 1px solid #3a3830 !important;
    border-radius: 8px !important;
    color: #faf9f5 !important;
    font-family: 'Poppins', sans-serif !important;
    transition: border-color 0.2s !important;
}
[data-testid="stSelectbox"] > div > div:hover {
    border-color: #d97757 !important;
}
[data-testid="stSelectbox"] label {
    font-family: 'Poppins', sans-serif !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    color: #b0aea5 !important;
}

/* ── Expanders ────────────────────────────────────────────────── */
.stExpander {
    background-color: #1e1d1b !important;
    border: 1px solid #2a2925 !important;
    border-radius: 10px !important;
    margin-bottom: 8px !important;
    overflow: hidden !important;
    animation: fadeInUp 0.35s ease !important;
    transition: border-color 0.2s !important;
}
.stExpander:hover { border-color: #3a3830 !important; }
.stExpander summary {
    font-family: 'Poppins', sans-serif !important;
    font-weight: 600 !important;
    color: #faf9f5 !important;
    padding: 14px 16px !important;
}

/* ── Alerts / info boxes ──────────────────────────────────────── */
[data-testid="stAlert"] {
    border-radius: 10px !important;
    border: 1px solid !important;
    font-family: 'Lora', serif !important;
}
[data-testid="stAlert"][kind="info"] {
    background: rgba(106, 155, 204, 0.08) !important;
    border-color: rgba(106, 155, 204, 0.25) !important;
}
[data-testid="stAlert"][kind="success"] {
    background: rgba(120, 140, 93, 0.1) !important;
    border-color: rgba(120, 140, 93, 0.3) !important;
}
[data-testid="stAlert"][kind="warning"] {
    background: rgba(217, 119, 87, 0.08) !important;
    border-color: rgba(217, 119, 87, 0.25) !important;
}
[data-testid="stAlert"][kind="error"] {
    background: rgba(239, 68, 68, 0.08) !important;
    border-color: rgba(239, 68, 68, 0.25) !important;
}

/* ── Dividers ─────────────────────────────────────────────────── */
hr { border-color: #2a2925 !important; margin: 1.5rem 0 !important; }

/* ── Chat messages ────────────────────────────────────────────── */
[data-testid="stChatMessage"] {
    background-color: #1e1d1b !important;
    border: 1px solid #2a2925 !important;
    border-radius: 12px !important;
    margin-bottom: 8px !important;
    animation: fadeInUp 0.3s ease !important;
    font-family: 'Lora', serif !important;
}
[data-testid="stChatMessage"][data-testid*="assistant"] {
    border-left: 3px solid #d97757 !important;
}

/* ── Chat input ───────────────────────────────────────────────── */
[data-testid="stChatInput"] textarea {
    background-color: #1e1d1b !important;
    border: 1px solid #3a3830 !important;
    border-radius: 10px !important;
    color: #faf9f5 !important;
    font-family: 'Lora', serif !important;
}

/* ── Metrics ──────────────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: #1e1d1b;
    border: 1px solid #2a2925;
    border-radius: 10px;
    padding: 16px;
}
[data-testid="stMetricLabel"] {
    font-family: 'Poppins', sans-serif !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.1em !important;
    color: #b0aea5 !important;
}
[data-testid="stMetricValue"] {
    font-family: 'Poppins', sans-serif !important;
    font-weight: 700 !important;
    color: #faf9f5 !important;
}

/* ── Spinner ──────────────────────────────────────────────────── */
[data-testid="stSpinner"] { color: #d97757 !important; }

/* ── Custom card components ───────────────────────────────────── */
.irac-card {
    background: #1e1d1b;
    border: 1px solid #2a2925;
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 0.75rem;
    animation: fadeInUp 0.4s ease;
    transition: border-color 0.2s;
}
.irac-card:hover { border-color: #3a3830; }
.irac-card-accent { border-left: 3px solid #d97757; }
.irac-card-blue { border-left: 3px solid #6a9bcc; }
.irac-card-green { border-left: 3px solid #788c5d; }
.irac-card-red { border-left: 3px solid #ef4444; }

.section-label {
    font-family: 'Poppins', sans-serif;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: #d97757;
    margin-bottom: 6px;
}

.word-count-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin: 6px 0 4px 0;
    font-family: 'Poppins', sans-serif;
    font-size: 11px;
}
.word-count-num { font-weight: 600; }
.word-count-target { color: #b0aea5; }
.word-count-bar-bg {
    height: 3px;
    background: #2a2925;
    border-radius: 2px;
    overflow: hidden;
    margin-bottom: 12px;
}
.word-count-bar-fill {
    height: 100%;
    border-radius: 2px;
    transition: width 0.4s ease;
}

.tip-box {
    background: rgba(106, 155, 204, 0.06);
    border: 1px solid rgba(106, 155, 204, 0.2);
    border-radius: 8px;
    padding: 10px 14px;
    margin-bottom: 12px;
    font-family: 'Lora', serif;
    font-size: 13px;
    color: #b0aea5;
    line-height: 1.6;
}
.tip-box-label {
    font-family: 'Poppins', sans-serif;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #6a9bcc;
    margin-bottom: 4px;
}

.grade-circle {
    width: 56px;
    height: 56px;
    border-radius: 50%;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-family: 'Poppins', sans-serif;
    font-size: 20px;
    font-weight: 700;
    animation: scaleIn 0.4s ease;
}
.grade-a  { background: rgba(120,140,93,0.2); color: #788c5d; border: 2px solid #788c5d; }
.grade-b  { background: rgba(106,155,204,0.2); color: #6a9bcc; border: 2px solid #6a9bcc; }
.grade-c  { background: rgba(217,119,87,0.2); color: #d97757; border: 2px solid #d97757; }
.grade-df { background: rgba(239,68,68,0.2); color: #ef4444; border: 2px solid #ef4444; }

.score-pill {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-family: 'Poppins', sans-serif;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.04em;
}
.pill-excellent { background: rgba(120,140,93,0.15); color: #788c5d; border: 1px solid rgba(120,140,93,0.3); }
.pill-good { background: rgba(106,155,204,0.15); color: #6a9bcc; border: 1px solid rgba(106,155,204,0.3); }
.pill-needs-work { background: rgba(217,119,87,0.15); color: #d97757; border: 1px solid rgba(217,119,87,0.3); }
.pill-missing { background: rgba(239,68,68,0.15); color: #ef4444; border: 1px solid rgba(239,68,68,0.3); }

.feedback-col-header {
    font-family: 'Poppins', sans-serif;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #b0aea5;
    margin-bottom: 6px;
    padding-bottom: 6px;
    border-bottom: 1px solid #2a2925;
}

.insight-box {
    background: rgba(217, 119, 87, 0.08);
    border: 1px solid rgba(217, 119, 87, 0.25);
    border-left: 3px solid #d97757;
    border-radius: 8px;
    padding: 14px 16px;
    font-family: 'Lora', serif;
    font-size: 14px;
    color: #e8e6dc;
    margin: 1rem 0;
    animation: fadeInUp 0.4s ease;
}
.insight-label {
    font-family: 'Poppins', sans-serif;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: #d97757;
    margin-bottom: 6px;
}

/* ── Animations ───────────────────────────────────────────────── */
@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}
@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}
@keyframes scaleIn {
    from { transform: scale(0.6); opacity: 0; }
    to { transform: scale(1); opacity: 1; }
}
@keyframes slideInRight {
    from { opacity: 0; transform: translateX(16px); }
    to { opacity: 1; transform: translateX(0); }
}
@keyframes timerPulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}
</style>
""", unsafe_allow_html=True)
