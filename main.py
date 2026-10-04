"""
main.py - Streamlit dashboard for DevOps Autopilot (UI only).

Dark dashboard: sidebar navigation, incident form, agent workflow, summary,
live activity, and the GitHub / Slack / human-approval actions.
All AI, GitHub and Slack work lives in agent_brain.py, github_service.py
and slack_service.py.

Run with:  streamlit run app/main.py
"""

import sys

# Streamlit Cloud ships an old SQLite that CrewAI's dependency rejects.
# If pysqlite3 is installed (Linux), use it instead. Must run before crewai loads.
try:
    __import__("pysqlite3")
    sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
except ImportError:
    pass

import logging  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from html import escape  # noqa: E402

import streamlit as st  # noqa: E402

st.set_page_config(page_title="DevOps Autopilot", page_icon="🛠️", layout="wide")

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("devops_autopilot.main")

import agent_brain  # noqa: E402
import github_service  # noqa: E402
import slack_service  # noqa: E402

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

SAMPLE_INCIDENT = {
    "inp_service": "Payment API",
    "inp_error_rate": "38",
    "inp_http_status": "500",
    "inp_error": "AttributeError: 'NoneType' object has no attribute 'email'",
    "inp_trace": (
        "Traceback (most recent call last):\n"
        '  File "/app/api/routes.py", line 42, in handle_payment\n'
        "    result = process_customer(customer_id)\n"
        '  File "/app/services/customer_service.py", line 18, in process_customer\n'
        "    return send_receipt(customer.email)\n"
        "AttributeError: 'NoneType' object has no attribute 'email'"
    ),
}

STAGES = [
    ("monitor", "Monitor Agent", "Reads the incident and classifies severity", "#2F8CFF", "eye"),
    ("diagnoser", "Diagnoser & Fixer", "Finds the root cause and proposes a patch", "#8B5CF6", "search"),
    ("guard", "Guard & Orchestrator", "Reviews risk and asks a human to decide", "#F5B82E", "shield"),
]

STAGE_EVENTS = {
    ("monitor", "running"): ("monitor", "Analyzing the incident report..."),
    ("monitor", "done"): ("monitor", "Incident report ready"),
    ("diagnoser", "running"): ("diagnoser", "Inspecting stack trace and source code..."),
    ("diagnoser", "done"): ("diagnoser", "Root cause identified, fix proposed"),
    ("guard", "running"): ("guard", "Reviewing the patch for safety..."),
    ("guard", "done"): ("guard", "Risk assessed. Validation: NOT RUN. Approval: PENDING"),
}

TAG_COLORS = {
    "monitor": "#2F8CFF", "diagnoser": "#8B5CF6", "guard": "#F5B82E",
    "github": "#4ADE80", "slack": "#F472B6", "human": "#E6EBFA", "system": "#8C97B8",
}
LEVEL_COLORS = {"LOW": "#4ADE80", "MEDIUM": "#F5B82E", "HIGH": "#FF6B7A", "CRITICAL": "#FF6B7A"}

CONFIG_GROUPS = {
    "Groq": ["GROQ_API_KEY"],
    "GitHub": ["GITHUB_TOKEN", "GITHUB_REPO_OWNER", "GITHUB_REPO_NAME"],
    "Slack": ["SLACK_BOT_TOKEN", "SLACK_CHANNEL_ID"],
}

SVG_OPEN = ('<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#ffffff" '
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">')
ICONS = {
    "eye": SVG_OPEN + '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>',
    "search": SVG_OPEN + '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>',
    "shield": SVG_OPEN + '<path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z"/><path d="M9 12l2 2 4-4"/></svg>',
    "alert": SVG_OPEN + '<circle cx="12" cy="12" r="9"/><path d="M12 8v5"/><path d="M12 16.5v.01"/></svg>',
}

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=JetBrains+Mono:wght@400;700&display=swap');
.stApp{background:#070B1A;font-family:'DM Sans',system-ui,sans-serif}
[data-testid="stHeader"]{background:transparent}
#MainMenu,footer{visibility:hidden}
.block-container{max-width:1280px;padding-top:1.2rem;padding-bottom:4rem}
[data-testid="stSidebar"]{background:#080E22;border-right:1px solid #16213F}
[data-testid="stSidebar"] .block-container{padding-top:1.5rem}
.stApp p,.stApp li,.stApp label{color:#C9D2EC}
[data-testid="stWidgetLabel"] p{font-size:13px;color:#9AA6C6}
.stTextInput input,.stTextArea textarea{background:#0A1228!important;color:#E6EBFA!important;border:1px solid #22305C!important;border-radius:10px!important;font-size:14px!important}
[data-baseweb="input"],[data-baseweb="textarea"],[data-baseweb="base-input"]{background:#0A1228!important;border-radius:10px!important;border-color:#22305C!important}
.stTextInput input::placeholder,.stTextArea textarea::placeholder{color:#5F6B90!important}
.stButton>button,.stLinkButton>a{border-radius:12px;min-height:44px;font-weight:700;border:1px solid #22305C;background:#0F1A3A;color:#E6EBFA}
.stButton>button p,.stLinkButton>a p{color:inherit!important;font-weight:700}
.stButton>button:hover,.stLinkButton>a:hover{border-color:#3B82F6;color:#7FB2FF}
.stButton>button[kind="primary"],.stButton>button[data-testid="stBaseButton-primary"]{background:linear-gradient(135deg,#2F6BFF,#3B82F6);border-color:#3B82F6;color:#fff;box-shadow:0 6px 20px rgba(47,107,255,.35)}
.stButton>button[kind="primary"]:hover,.stButton>button[data-testid="stBaseButton-primary"]:hover{color:#fff;filter:brightness(1.1)}
[class*="st-key-nav_"] button{justify-content:flex-start;background:transparent;border:0;color:#AEBBDD;min-height:48px;box-shadow:none}
[class*="st-key-nav_"] button:hover{background:#101B3D;color:#E6EBFA;border:0}
[class*="st-key-card_"]{background:#0D1530;border:1px solid #1B2750;border-radius:18px;padding:20px}
[data-testid="stAlert"]{background:#121D42;border:1px solid #22305C;border-radius:12px}
[data-testid="stAlert"] *{color:#E6EBFA!important}
.ap-top{display:flex;justify-content:flex-end;align-items:center;gap:14px;margin-bottom:6px}
.ap-chip{display:flex;align-items:center;gap:8px;font-size:14px;font-weight:500}
.ap-dot{width:10px;height:10px;border-radius:50%}
.ap-avatar{width:38px;height:38px;border-radius:50%;background:#16275A;color:#7FB2FF;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px}
.ap-welcome{color:#9AA6C6;font-size:16px}
.ap-hero{font-size:34px;font-weight:700;color:#E6EBFA;margin:2px 0}
.ap-tag{color:#9AA6C6;font-size:16px}
.ap-banner{display:inline-block;background:#101D45;border:1px solid #1B2A5C;border-radius:14px;padding:12px 20px;color:#AEBBDD;font-size:14px}
.ap-brand{display:flex;align-items:center;gap:12px;margin-bottom:22px}
.ap-logo{width:44px;height:44px;border-radius:12px;background:linear-gradient(135deg,#2F6BFF,#8B5CF6);color:#fff;display:flex;align-items:center;justify-content:center;font:700 16px 'JetBrains Mono',monospace}
.ap-bt{font-size:18px;font-weight:700;color:#E6EBFA}
.ap-bs{font-size:12px;color:#8C97B8}
.ap-promo{background:#0D1733;border:1px solid #16213F;border-radius:16px;padding:18px;margin-top:40px}
.ap-promo b{color:#7FB2FF;font-size:18px;line-height:1.35;display:block;margin-bottom:8px}
.ap-card{background:#0D1530;border:1px solid #1B2750;border-radius:18px;padding:20px;margin-bottom:16px}
.ap-ch{display:flex;align-items:center;gap:12px;margin-bottom:14px}
.ap-ci{width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.ap-ct{font-size:17px;font-weight:700;color:#E6EBFA;flex:1}
.ap-h{font-size:17px;font-weight:700;color:#E6EBFA;margin-bottom:8px}
.ap-lbl{font-size:12px;color:#8C97B8;margin:12px 0 4px}
.ap-val{font-size:15px;font-weight:700;color:#7FB2FF}
.ap-text{color:#C9D2EC;line-height:1.6;font-size:15px}
.ap-muted{color:#8C97B8;font-size:14px;line-height:1.5}
.ap-pill{display:inline-block;font-size:12px;font-weight:700;padding:5px 12px;border-radius:999px}
.ap-step{display:flex;align-items:flex-start;gap:14px}
.ap-ico{width:54px;height:54px;border-radius:50%;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.ap-ico.run{animation:apPulse 1.4s ease-in-out infinite}
.ap-line{width:2px;height:26px;margin:4px 0 4px 26px}
@keyframes apPulse{
0%{box-shadow:0 0 0 0 rgba(59,130,246,.6)}
70%{box-shadow:0 0 0 12px rgba(59,130,246,0)}
100%{box-shadow:0 0 0 0 rgba(59,130,246,0)}
}
.ap-row{display:flex;justify-content:space-between;align-items:center;padding:9px 0;border-bottom:1px solid #16213F;font-size:14px;color:#C9D2EC}
.ap-row:last-child{border-bottom:0}
.ap-act{display:flex;align-items:flex-start;gap:14px;padding:12px 0;border-bottom:1px solid #16213F}
.ap-act:last-child{border-bottom:0}
.ap-adot{width:12px;height:12px;border-radius:50%;margin-top:5px;flex-shrink:0}
.ap-time{margin-left:auto;color:#8C97B8;font-size:13px;white-space:nowrap}
.ap-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px;margin:6px 0 16px}
.ap-tile{background:#0D1530;border:1px solid #1B2750;border-radius:16px;padding:16px}
.ap-big{font-size:26px;font-weight:700;margin-top:4px}
.ap-bar{height:6px;background:#1B2750;border-radius:99px;margin-top:10px}
.ap-bar>div{height:6px;border-radius:99px;background:#FF6B7A}
.ap-code{background:#060A16;border:1px solid #1B2750;border-radius:12px;padding:14px 16px;font:13px/1.8 'JetBrains Mono',monospace;overflow-x:auto;white-space:pre-wrap}
.ap-file{display:inline-block;font:13px 'JetBrains Mono',monospace;background:#14214D;color:#7FB2FF;padding:5px 11px;border-radius:8px;margin:4px 6px 4px 0}
.ap-note{background:#2A2210;border:1px solid #5C4A1A;color:#FFD98A;border-radius:12px;padding:12px 16px;margin:6px 0;font-size:14px}
.ap-foot{text-align:center;font-size:12px;color:#8C97B8;margin-top:24px}
</style>
"""


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def h(text) -> str:
    """Escape text for safe use inside HTML shown with st.markdown."""
    value = "" if text is None else str(text)
    return escape(value, quote=True).replace("$", "&#36;").replace("\n", "<br>")


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def add_event(tag: str, message: str) -> None:
    events = st.session_state["events"]
    events.append((tag, message, now_utc()))
    del events[:-80]


def init_state() -> None:
    defaults = {
        "view": "home", "result": None, "incident_id": None, "pr_info": None,
        "slack_info": None, "approval": "PENDING", "events": [], "incident": {},
        "opened_at": "", "stage_states": {key: "waiting" for key, *_ in STAGES},
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)
    # Re-assigning keeps typed values alive while the user visits other views.
    for key in SAMPLE_INCIDENT:
        st.session_state[key] = st.session_state.get(key, "")


def go(view: str) -> None:
    st.session_state["view"] = view


def load_sample() -> None:
    for key, value in SAMPLE_INCIDENT.items():
        st.session_state[key] = value


def reset_incident() -> None:
    st.session_state.update(
        view="home", result=None, incident_id=None, pr_info=None, slack_info=None,
        approval="PENDING", events=[], incident={}, opened_at="",
        stage_states={key: "waiting" for key, *_ in STAGES})


def decide(state: str) -> None:
    st.session_state["approval"] = state
    add_event("human", f"{state}. Merge and deployment stay manual.")
    logger.info("Fix %s by reviewer", state.lower())


def is_configured(group: str) -> bool:
    return not agent_brain.get_missing_env(CONFIG_GROUPS[group])


# --------------------------------------------------------------------------
# HTML renderers
# --------------------------------------------------------------------------

def card_head(icon_key: str, color: str, title: str, right: str = "") -> str:
    return (f'<div class="ap-ch"><div class="ap-ci" style="background:{color}33;color:{color}">'
            f'<span style="font-weight:700">&#9679;</span></div><div class="ap-ct">{h(title)}</div>{right}</div>')


def render_topbar() -> None:
    ready = is_configured("Groq")
    color, text = ("#4ADE80", "Ready") if ready else ("#F5B82E", "Setup needed")
    st.markdown(
        f'<div class="ap-top"><div class="ap-chip" style="color:{color}">'
        f'<span class="ap-dot" style="background:{color}"></span>{h(text)}</div>'
        '<div class="ap-avatar">DE</div></div>'
        '<div class="ap-welcome">Welcome back, DevOps Engineer</div>'
        '<div class="ap-hero">DevOps Autopilot</div>'
        '<div class="ap-tag">AI agents. Real fixes. Happier systems.</div>'
        '<div style="margin:14px 0 18px"><span class="ap-banner">From incident &rarr; to resolution, '
        'with a human in the loop</span></div>',
        unsafe_allow_html=True)


def render_workflow(box) -> None:
    pills = {
        "waiting": ("Waiting", "#8C97B8", "#16213F"),
        "running": ("In Progress", "#7FB2FF", "#12306B"),
        "done": ("Completed", "#4ADE80", "#0F3B2C"),
        "failed": ("Failed", "#FF6B7A", "#40161F"),
    }
    parts = ['<div class="ap-card" style="min-height:470px"><div class="ap-h" style="margin-bottom:18px">Agent Workflow</div>']
    for i, (key, name, sub, color, icon) in enumerate(STAGES):
        state = st.session_state["stage_states"][key]
        label, fg, bg = pills[state]
        ring = " run" if state == "running" else ""
        parts.append(
            f'<div class="ap-step"><div class="ap-ico{ring}" style="background:{color}">{ICONS[icon]}</div>'
            f'<div><div style="font-size:16px;font-weight:700;color:#E6EBFA">{h(name)}</div>'
            f'<div class="ap-muted" style="margin:2px 0 8px">{h(sub)}</div>'
            f'<span class="ap-pill" style="color:{fg};background:{bg}">{label}</span></div></div>')
        if i < len(STAGES) - 1:
            parts.append(f'<div class="ap-line" style="background:{color}"></div>')
    parts.append("</div>")
    box.markdown("".join(parts), unsafe_allow_html=True)


def render_summary(box) -> None:
    result = st.session_state["result"]
    incident = st.session_state["incident"] or {
        "service": st.session_state.get("inp_service", ""),
        "error_rate": st.session_state.get("inp_error_rate", ""),
        "http_status": st.session_state.get("inp_http_status", ""),
    }
    severity = result["incident_report"]["severity"] if result else ""
    pill = ""
    if severity:
        color = LEVEL_COLORS.get(severity, "#E6EBFA")
        pill = f'<span class="ap-pill" style="color:{color};background:{color}22">{h(severity)}</span>'
    rate = str(incident.get("error_rate", "")).strip()
    box.markdown(
        '<div class="ap-card"><div class="ap-ch"><div class="ap-ci" style="background:#FF6B7A33">'
        f'<span style="color:#FF6B7A;font-weight:700">!</span></div><div class="ap-ct">Incident Summary</div>{pill}</div>'
        f'<div class="ap-lbl">Service</div><div class="ap-val">{h(incident.get("service") or "-")}</div>'
        f'<div class="ap-lbl">Error Rate</div><div class="ap-val">{h(rate + "%" if rate else "-")}</div>'
        f'<div class="ap-lbl">HTTP Status</div><div class="ap-val">{h(incident.get("http_status") or "-")}</div>'
        f'<div class="ap-lbl">Opened (UTC)</div><div class="ap-val" style="color:#E6EBFA">'
        f'{h(st.session_state["opened_at"] or "-")}</div></div>',
        unsafe_allow_html=True)


def row(label: str, value: str, color: str = "#E6EBFA") -> str:
    return (f'<div class="ap-row"><span>{h(label)}</span>'
            f'<span style="color:{color};font-weight:700">{h(value)}</span></div>')


def render_session(box) -> None:
    result = st.session_state["result"]
    approval = st.session_state["approval"]
    approval_color = {"PENDING": "#F5B82E", "APPROVED": "#4ADE80", "REJECTED": "#FF6B7A"}[approval]
    pr = st.session_state["pr_info"]
    box.markdown(
        '<div class="ap-card"><div class="ap-h">Session Status</div>'
        + row("Incident ID", st.session_state["incident_id"] or "-")
        + row("Validation", result["validation_status"] if result else "-", "#8C97B8")
        + row("GitHub PR", f"#{pr['number']}" if pr else "not created", "#4ADE80" if pr else "#8C97B8")
        + row("Slack alert", "sent" if st.session_state["slack_info"] else "not sent",
              "#4ADE80" if st.session_state["slack_info"] else "#8C97B8")
        + row("Approval", approval if result else "-", approval_color if result else "#8C97B8")
        + "</div>",
        unsafe_allow_html=True)


def render_services() -> None:
    parts = ['<div class="ap-card"><div class="ap-h">Connected Services</div>']
    for name in CONFIG_GROUPS:
        ok = is_configured(name)
        color, bg, text = ("#4ADE80", "#0F3B2C", "Connected") if ok else ("#F5B82E", "#3A2D0B", "Not set")
        parts.append(f'<div class="ap-row"><span>{h(name)}</span>'
                     f'<span class="ap-pill" style="color:{color};background:{bg}">{text}</span></div>')
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def activity_html(events, limit: int) -> str:
    if not events:
        return '<div class="ap-muted">No activity yet. Load the sample incident and press Start Analysis.</div>'
    parts = []
    for tag, msg, when in events[-limit:][::-1]:
        parts.append(
            f'<div class="ap-act"><div class="ap-adot" style="background:{TAG_COLORS.get(tag, "#8C97B8")}"></div>'
            f'<div><div style="font-weight:700;color:#E6EBFA">{h(tag.capitalize())}</div>'
            f'<div class="ap-muted">{h(msg)}</div></div><div class="ap-time">{h(when)} UTC</div></div>')
    return "".join(parts)


def render_activity(box) -> None:
    box.markdown('<div class="ap-card"><div class="ap-h">Live Activity</div>'
                 + activity_html(st.session_state["events"], 8) + "</div>",
                 unsafe_allow_html=True)


def tile(label: str, value: str, color: str = "#E6EBFA", bar=None) -> str:
    bar_html = ""
    if bar is not None:
        bar_html = f'<div class="ap-bar"><div style="width:{max(0, min(100, bar))}%"></div></div>'
    return (f'<div class="ap-tile"><div class="ap-lbl" style="margin:0">{h(label)}</div>'
            f'<div class="ap-big" style="color:{color}">{h(value)}</div>{bar_html}</div>')


def diff_html(diff: str) -> str:
    lines = []
    for line in (diff or "").splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            color = "#7BE3B0"
        elif line.startswith("-") and not line.startswith("---"):
            color = "#FF9B9B"
        else:
            color = "#8C97B8"
        text = escape(line or " ", quote=True).replace("$", "&#36;")
        lines.append(f'<span style="color:{color}">{text}</span>')
    return "<br>".join(lines)


# --------------------------------------------------------------------------
# Sections
# --------------------------------------------------------------------------

def sidebar() -> None:
    sb = st.sidebar
    sb.markdown('<div class="ap-brand"><div class="ap-logo">AP</div><div>'
                '<div class="ap-bt">DevOps Autopilot</div>'
                '<div class="ap-bs">AI-Powered Incident Response</div></div></div>',
                unsafe_allow_html=True)
    sb.button("Home", key="nav_home", icon=":material/home:", use_container_width=True,
              on_click=go, args=("home",))
    sb.button("New Incident", key="nav_new", icon=":material/bolt:", use_container_width=True,
              on_click=reset_incident)
    sb.button("Settings", key="nav_settings", icon=":material/settings:", use_container_width=True,
              on_click=go, args=("settings",))
    sb.button("Logs", key="nav_logs", icon=":material/description:", use_container_width=True,
              on_click=go, args=("logs",))
    active = {"home": "nav_home", "settings": "nav_settings", "logs": "nav_logs"}[st.session_state["view"]]
    sb.markdown(f'<style>.st-key-{active} button{{background:#12214A!important;color:#7FB2FF!important}}</style>',
                unsafe_allow_html=True)
    sb.markdown('<div class="ap-promo"><b>Smarter Ops.<br>Faster Recovery.</b>'
                '<div class="ap-muted">Prototype: AI proposes, a human approves. '
                'Nothing is deployed automatically.</div></div>', unsafe_allow_html=True)


def settings_view() -> None:
    st.markdown('<div class="ap-hero">Settings</div><div class="ap-tag" style="margin-bottom:16px">'
                'Which services are configured (values are never shown).</div>', unsafe_allow_html=True)
    parts = ['<div class="ap-card">']
    for name, names in CONFIG_GROUPS.items():
        missing = agent_brain.get_missing_env(names)
        color, text = ("#4ADE80", "Configured") if not missing else ("#F5B82E", "Missing: " + ", ".join(missing))
        parts.append(row(name, text, color))
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)
    st.markdown(
        '<div class="ap-card"><div class="ap-h">Prototype limitations</div>'
        '<div class="ap-text">&bull; Incident source is manual / simulated.<br>'
        '&bull; Deployment is not automated; approval only records a decision.<br>'
        '&bull; Button approval is a prototype, not production-grade authorization.<br>'
        '&bull; Validation is always NOT RUN (no sandbox).<br>'
        '&bull; AI-generated patches need human review.</div></div>',
        unsafe_allow_html=True)


def logs_view() -> None:
    st.markdown('<div class="ap-hero">Logs</div><div class="ap-tag" style="margin-bottom:16px">'
                'Everything that happened in this session.</div>', unsafe_allow_html=True)
    st.markdown('<div class="ap-card">' + activity_html(st.session_state["events"], 80) + "</div>",
                unsafe_allow_html=True)


def show_results(result: dict) -> None:
    report, diag = result["incident_report"], result["diagnosis"]
    guard, patch = result["guard_review"], result["patch"]
    incident = st.session_state["incident"]

    for warning in result["warnings"]:
        st.markdown(f'<div class="ap-note">{h(warning)}</div>', unsafe_allow_html=True)

    try:
        rate = float(str(incident.get("error_rate", "")).strip() or "nan")
    except ValueError:
        rate = float("nan")
    no_rate = rate != rate
    severity, risk = report["severity"], result["final_risk"]
    approval = st.session_state["approval"]
    approval_color = {"PENDING": "#F5B82E", "APPROVED": "#4ADE80", "REJECTED": "#FF6B7A"}[approval]
    st.markdown(
        '<div class="ap-grid">'
        + tile("Error rate", "n/a" if no_rate else f"{rate:g}%", "#E6EBFA", None if no_rate else rate)
        + tile("Severity", severity, LEVEL_COLORS.get(severity, "#E6EBFA"))
        + tile("Risk level", risk, LEVEL_COLORS.get(risk, "#E6EBFA"))
        + tile("Validation", result["validation_status"], "#8C97B8")
        + tile("Approval", approval, approval_color)
        + "</div>",
        unsafe_allow_html=True)

    left, right = st.columns(2, gap="large")
    with left:
        st.markdown(
            '<div class="ap-card"><div class="ap-h">Incident summary</div>'
            f'<div class="ap-text">{h(guard["incident_summary"])}</div>'
            '<div class="ap-lbl">Service / detected error</div>'
            f'<div class="ap-muted">{h(report["affected_service"])} / {h(report["detected_error"])}</div>'
            '<div class="ap-lbl">Initial observation</div>'
            f'<div class="ap-text">{h(report["initial_observation"])}</div></div>'
            '<div class="ap-card"><div class="ap-h">Root cause</div>'
            f'<div class="ap-text">{h(diag["root_cause"])}</div>'
            f'<div style="margin-top:10px"><span class="ap-file">{h(diag["affected_file"])}</span>'
            f'<span class="ap-file">{h(diag["affected_function"])}</span></div>'
            f'<div class="ap-lbl">Why it happened</div><div class="ap-text">{h(diag["explanation"])}</div></div>',
            unsafe_allow_html=True)
    with right:
        diff_block = f'<div class="ap-code">{diff_html(patch["diff"])}</div>' if patch["diff"] else ""
        tests = "".join(f'<div class="ap-text">&bull; {h(t)}</div>' for t in diag["test_plan"])
        concerns = "".join(f'<div class="ap-text">&#9888; {h(c)}</div>' for c in guard["concerns"])
        st.markdown(
            '<div class="ap-card"><div class="ap-h">Proposed fix</div>'
            f'<div class="ap-text" style="margin-bottom:10px">{h(diag["proposed_fix"])}</div>'
            f'{diff_block}<div class="ap-muted" style="margin-top:10px">Patch status: {h(patch["reason"])}</div></div>'
            '<div class="ap-card"><div class="ap-h">Test / validation</div>'
            '<div class="ap-note">Validation: NOT RUN. No tests were executed; these are only recommendations.</div>'
            f'{tests}</div>'
            '<div class="ap-card"><div class="ap-h">Guard review</div>'
            f'<div class="ap-text"><b>Risk reasoning:</b> {h(guard["risk_reasoning"])}</div>'
            f'<div class="ap-text" style="margin-top:6px"><b>Recommendation:</b> {h(guard["recommendation"])}</div>'
            f'{concerns}</div>',
            unsafe_allow_html=True)


def pr_card(result: dict) -> None:
    st.markdown('<div class="ap-h">GitHub pull request</div>', unsafe_allow_html=True)
    pr = st.session_state["pr_info"]
    if pr:
        kind = "code change" if pr["mode"] == "code_change" else "proposal document only"
        st.markdown(
            f'<div class="ap-text" style="color:#4ADE80">PR #{h(pr["number"])} created ({h(kind)})</div>'
            f'<div class="ap-muted">branch {h(pr["branch"])}</div>', unsafe_allow_html=True)
        st.link_button("Open pull request", pr["url"])
        return
    st.markdown('<div class="ap-muted">Creates a branch and a Pull Request. '
                'Nothing is merged or pushed to main.</div>', unsafe_allow_html=True)
    if not st.button("Create GitHub PR", key="btn_pr", type="primary"):
        return
    report, diag, patch = result["incident_report"], result["diagnosis"], result["patch"]
    body = github_service.build_pr_body(st.session_state["incident_id"], report, diag,
                                        result["guard_review"], patch, result["final_risk"])
    created = None
    try:
        with st.spinner("Creating pull request..."):
            created = github_service.create_fix_pull_request(
                incident_id=st.session_state["incident_id"],
                title=f"[DevOps Autopilot] {report['incident_summary'][:80]}",
                body=body,
                file_path=patch["file_path"] if patch["applied"] else None,
                new_content=patch["new_content"] if patch["applied"] else None,
                proposal_markdown=body,
            )
    except github_service.GitHubServiceError as exc:
        st.error(str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.error("PR creation failed: %s", type(exc).__name__)
        st.error("An unexpected error occurred while creating the pull request.")
    if created:
        st.session_state["pr_info"] = created
        add_event("github", f"Pull request #{created['number']} opened")
        st.rerun()


def slack_card(result: dict) -> None:
    st.markdown('<div class="ap-h">Slack approval request</div>', unsafe_allow_html=True)
    if st.session_state["slack_info"]:
        st.markdown('<div class="ap-text" style="color:#4ADE80">Approval request sent to Slack.</div>',
                    unsafe_allow_html=True)
        return
    st.markdown('<div class="ap-muted">Posts the summary and PR link to your incident channel.</div>',
                unsafe_allow_html=True)
    if not st.button("Send to Slack", key="btn_slack", type="primary"):
        return
    sent = None
    try:
        with st.spinner("Sending to Slack..."):
            sent = slack_service.send_incident_alert(
                incident_id=st.session_state["incident_id"],
                report=result["incident_report"], diagnosis=result["diagnosis"],
                risk_level=result["final_risk"],
                validation_status=result["validation_status"],
                pr_info=st.session_state["pr_info"],
                approval_status=st.session_state["approval"],
            )
    except slack_service.SlackServiceError as exc:
        st.error(str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.error("Slack failed: %s", type(exc).__name__)
        st.error("An unexpected error occurred while contacting Slack.")
    if sent:
        st.session_state["slack_info"] = sent
        add_event("slack", "Approval request sent")
        st.rerun()


def gate_card() -> None:
    state = st.session_state["approval"]
    title, color, text = {
        "PENDING": ("LOCKED / PENDING", "#F5B82E",
                    "A human must approve before any merge or deployment."),
        "APPROVED": ("APPROVED", "#4ADE80",
                     "Next step: review and merge the PR on GitHub yourself. "
                     "This app does not merge or deploy anything."),
        "REJECTED": ("REJECTED", "#FF6B7A", "Rejected. No further action will be taken."),
    }[state]
    st.markdown(
        '<div class="ap-h">Human approval</div>'
        f'<div style="font-weight:700;color:{color}">{h(title)}</div>'
        f'<div class="ap-muted" style="margin:8px 0 12px">{h(text)}</div>',
        unsafe_allow_html=True)
    if state == "PENDING":
        col1, col2 = st.columns(2)
        col1.button("Approve fix", key="btn_approve", type="primary",
                    on_click=decide, args=("APPROVED",))
        col2.button("Reject fix", key="btn_reject", on_click=decide, args=("REJECTED",))
    else:
        st.button("Start new incident", key="btn_reset", on_click=reset_incident)


# --------------------------------------------------------------------------
# Home page
# --------------------------------------------------------------------------

def home_view() -> None:
    render_topbar()
    form_col, flow_col, side_col = st.columns([1.35, 1, 0.9], gap="medium")

    with form_col:
        with st.container(border=True, key="card_incident"):
            st.markdown('<div class="ap-ch"><div class="ap-ci" style="background:#FF6B7A33">'
                        '<span style="color:#FF6B7A;font-weight:700">&#9679;</span></div>'
                        '<div class="ap-ct">Current Incident</div></div>', unsafe_allow_html=True)
            st.text_input("Service Name", key="inp_service", placeholder="Payment API")
            c1, c2 = st.columns(2)
            c1.text_input("Error Rate (%)", key="inp_error_rate", placeholder="38")
            c2.text_input("HTTP Status Code", key="inp_http_status", placeholder="500")
            st.text_input("Error Message", key="inp_error", placeholder="AttributeError: ...")
            st.text_area("Stack Trace", key="inp_trace", height=140)
            b1, b2 = st.columns([1, 1])
            analyze = b1.button("Start Analysis", type="primary", icon=":material/play_arrow:")
            b2.button("Load sample", on_click=load_sample)
    with flow_col:
        workflow_box = st.empty()
    with side_col:
        summary_box = st.empty()
        session_box = st.empty()
        render_services()

    activity_box = st.empty()

    def refresh() -> None:
        render_workflow(workflow_box)
        render_summary(summary_box)
        render_session(session_box)
        render_activity(activity_box)

    refresh()

    if analyze:
        if agent_brain.get_missing_env(["GROQ_API_KEY"]):
            st.error("Missing configuration: GROQ_API_KEY. Add it to .env or Streamlit Secrets.")
        else:
            reset_incident()
            st.session_state["incident_id"] = agent_brain.generate_incident_id()
            st.session_state["opened_at"] = now_utc()
            incident = {
                "service": st.session_state["inp_service"],
                "error_rate": st.session_state["inp_error_rate"],
                "http_status": st.session_state["inp_http_status"],
                "error_message": st.session_state["inp_error"],
                "stack_trace": st.session_state["inp_trace"],
            }
            st.session_state["incident"] = incident
            add_event("system", f"Incident {st.session_state['incident_id']} received")
            refresh()

            def on_progress(stage: str, state: str) -> None:
                st.session_state["stage_states"][stage] = state
                event = STAGE_EVENTS.get((stage, state))
                if event:
                    add_event(*event)
                elif state == "failed":
                    add_event("system", f"{stage} agent failed")
                render_workflow(workflow_box)
                render_activity(activity_box)

            try:
                with st.spinner("Agents are working..."):
                    outcome = agent_brain.run_incident_response(incident, on_progress)
            except Exception as exc:  # noqa: BLE001 - last-resort guard
                logger.error("Unexpected failure: %s", type(exc).__name__)
                outcome = {"ok": False, "error": "An error occurred while processing the incident."}
            if outcome["ok"]:
                st.session_state["result"] = outcome
            else:
                add_event("system", "Analysis stopped")
                st.error(outcome["error"])
            refresh()

    result = st.session_state["result"]
    if result:
        show_results(result)
        a, b, c = st.columns(3, gap="large")
        with a:
            with st.container(border=True, key="card_pr"):
                pr_card(result)
        with b:
            with st.container(border=True, key="card_slack"):
                slack_card(result)
        with c:
            with st.container(border=True, key="card_gate"):
                gate_card()
        st.markdown('<div class="ap-foot">Prototype approval only. Not a production-grade '
                    'authorization system (no user identity, no audit trail).</div>',
                    unsafe_allow_html=True)


def main() -> None:
    init_state()
    st.markdown(THEME_CSS, unsafe_allow_html=True)
    sidebar()
    view = st.session_state["view"]
    if view == "settings":
        settings_view()
    elif view == "logs":
        logs_view()
    else:
        home_view()


main()
