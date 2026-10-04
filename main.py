"""
main.py - Streamlit dashboard for DevOps Autopilot (UI only).

Dark "mission control" theme. All AI / GitHub / Slack work lives in
agent_brain.py, github_service.py and slack_service.py.

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
    ("monitor", "Monitor Agent", "Reads the incident and classifies severity"),
    ("diagnoser", "Diagnoser & Fixer", "Finds the root cause and proposes a patch"),
    ("guard", "Guard & Orchestrator", "Reviews risk and asks a human to decide"),
]

STAGE_EVENTS = {
    ("monitor", "running"): ("monitor", "Analyzing the incident report"),
    ("monitor", "done"): ("monitor", "Incident report ready"),
    ("diagnoser", "running"): ("diagnoser", "Inspecting stack trace and source code"),
    ("diagnoser", "done"): ("diagnoser", "Root cause identified, fix proposed"),
    ("guard", "running"): ("guard", "Reviewing the patch for safety"),
    ("guard", "done"): ("guard", "Risk assessed. Validation: NOT RUN. Approval: PENDING"),
}

TAG_COLORS = {
    "monitor": "#7DD3FC", "diagnoser": "#C4B5FD", "guard": "#FCD34D",
    "github": "#86EFAC", "slack": "#F9A8D4", "human": "#FFFFFF", "system": "#FF9B9B",
}
LEVEL_COLORS = {"LOW": "#5BE3A0", "MEDIUM": "#FFB84D", "HIGH": "#FF6B6B", "CRITICAL": "#FF6B6B"}

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Space+Grotesk:wght@500;700&display=swap');
.stApp{background:#0B1020;font-family:'Space Grotesk',system-ui,sans-serif}
[data-testid="stHeader"]{background:transparent}
#MainMenu,footer{visibility:hidden}
.block-container{max-width:1180px;padding-top:2rem;padding-bottom:4rem}
[data-testid="stSidebar"]{background:#0A0F1E;border-right:1px solid #1F2A48}
.stApp p,.stApp li,.stApp label{color:#C9D2EC}
[data-testid="stWidgetLabel"] p{font:700 11px 'JetBrains Mono',monospace;letter-spacing:.08em;text-transform:uppercase;color:#8C97B8}
.stTextInput input,.stTextArea textarea{background:#0B1020!important;color:#E6EBFA!important;border:1px solid #2A3760!important;border-radius:12px!important;font-family:'JetBrains Mono',monospace!important;font-size:14px!important}
[data-baseweb="input"],[data-baseweb="textarea"],[data-baseweb="base-input"]{background:#0B1020!important;border-radius:12px!important;border-color:#2A3760!important}
.stTextInput input::placeholder,.stTextArea textarea::placeholder{color:#5F6B90!important}
.stTextInput input:focus,.stTextArea textarea:focus{outline:2px solid #4DE1C1!important}
.stButton>button,.stLinkButton>a{border-radius:12px;min-height:46px;font-weight:700;border:1px solid #2A3760;background:transparent;color:#E6EBFA}
.stButton>button p,.stLinkButton>a p{color:inherit!important;font-weight:700}
.stButton>button:hover,.stLinkButton>a:hover{border-color:#4DE1C1;color:#4DE1C1}
.stButton>button[kind="primary"],.stButton>button[data-testid="stBaseButton-primary"]{background:#4DE1C1;border-color:#4DE1C1;color:#06231D}
.stButton>button[kind="primary"]:hover,.stButton>button[data-testid="stBaseButton-primary"]:hover{color:#06231D;filter:brightness(1.08)}
.stButton>button:disabled{opacity:.45}
[class*="st-key-card_"]{background:#121A2F;border:1px solid #1F2A48;border-radius:20px;padding:22px}
[data-testid="stAlert"]{background:#162040;border:1px solid #2A3760;border-radius:14px}
[data-testid="stAlert"] *{color:#E6EBFA!important}
.ap-head{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:16px;margin-bottom:8px}
.ap-brand{display:flex;align-items:center;gap:14px}
.ap-logo{width:50px;height:50px;border-radius:14px;background:#4DE1C1;color:#06231D;display:flex;align-items:center;justify-content:center;font:700 18px 'JetBrains Mono',monospace}
.ap-title{font-size:24px;font-weight:700;letter-spacing:.02em;color:#E6EBFA}
.ap-sub{font:13px 'JetBrains Mono',monospace;color:#8C97B8}
.ap-chip{display:flex;align-items:center;gap:10px;border:1px solid #2A3760;border-radius:999px;padding:10px 18px;font:700 13px 'JetBrains Mono',monospace}
.ap-dot{width:10px;height:10px;border-radius:50%}
.ap-h{font-size:18px;font-weight:700;color:#E6EBFA;margin-bottom:6px}
.ap-lbl{font:700 11px 'JetBrains Mono',monospace;letter-spacing:.08em;text-transform:uppercase;color:#8C97B8;margin:10px 0 6px}
.ap-text{color:#C9D2EC;line-height:1.6;font-size:15px}
.ap-muted{color:#8C97B8;font-size:14px;line-height:1.5}
.ap-card{background:#121A2F;border:1px solid #1F2A48;border-radius:20px;padding:22px;margin-bottom:16px}
.ap-term{background:#0A0F1E;border:1px solid #1F2A48;border-radius:20px;padding:22px;min-height:330px;font:13px/1.6 'JetBrains Mono',monospace}
.ap-term-head{display:flex;justify-content:space-between;margin-bottom:12px;color:#8C97B8}
.ap-log-msg{color:#C9D2EC}
.ap-ring{width:44px;height:44px;border-radius:50%;display:flex;align-items:center;justify-content:center;font:700 17px 'JetBrains Mono',monospace;flex-shrink:0}
.ap-waiting{border:2px solid #2A3760;color:#8C97B8}
.ap-running{border:2px solid #4DE1C1;color:#4DE1C1;animation:apPulse 1.2s ease-in-out infinite}
.ap-done{background:#4DE1C1;color:#06231D}
.ap-failed{background:#FF6B6B;color:#2B0A0A}
@keyframes apPulse{
0%{box-shadow:0 0 0 0 rgba(77,225,193,.55)}
70%{box-shadow:0 0 0 12px rgba(77,225,193,0)}
100%{box-shadow:0 0 0 0 rgba(77,225,193,0)}
}
.ap-bar{height:6px;background:#1F2A48;border-radius:99px;margin-top:12px}
.ap-bar>div{height:6px;border-radius:99px}
.ap-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:16px;margin:8px 0 16px}
.ap-tile{background:#121A2F;border:1px solid #1F2A48;border-radius:20px;padding:20px}
.ap-big{font:700 28px 'Space Grotesk',sans-serif;margin-top:6px}
.ap-code{background:#070B17;border:1px solid #1F2A48;border-radius:14px;padding:14px 16px;font:13px/1.8 'JetBrains Mono',monospace;overflow-x:auto;white-space:pre-wrap}
.ap-file{display:inline-block;font:13px 'JetBrains Mono',monospace;background:#1A2547;color:#7DD3FC;padding:6px 12px;border-radius:8px;margin:4px 6px 4px 0}
.ap-note{background:#2A2210;border:1px solid #5C4A1A;color:#FFD98A;border-radius:14px;padding:12px 16px;margin:6px 0;font-size:14px}
.ap-foot{text-align:center;font:12px 'JetBrains Mono',monospace;color:#8C97B8;margin-top:24px}
</style>
"""


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def h(text) -> str:
    """Escape text for safe use inside HTML shown with st.markdown."""
    value = "" if text is None else str(text)
    return escape(value, quote=True).replace("$", "&#36;").replace("\n", "<br>")


def add_event(tag: str, message: str) -> None:
    events = st.session_state["events"]
    events.append((tag, message))
    del events[:-60]


def init_state() -> None:
    defaults = {
        "result": None, "incident_id": None, "pr_info": None, "slack_info": None,
        "approval": "PENDING", "events": [], "incident": {},
        "stage_states": {key: "waiting" for key, _, _ in STAGES},
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)
    for key in SAMPLE_INCIDENT:
        st.session_state.setdefault(key, "")


def load_sample() -> None:
    for key, value in SAMPLE_INCIDENT.items():
        st.session_state[key] = value


def reset_incident() -> None:
    st.session_state.update(
        result=None, incident_id=None, pr_info=None, slack_info=None, approval="PENDING",
        events=[], incident={}, stage_states={key: "waiting" for key, _, _ in STAGES})


def decide(state: str) -> None:
    st.session_state["approval"] = state
    add_event("human", f"{state}. Merge and deployment stay manual.")
    logger.info("Fix %s by reviewer", state.lower())


# --------------------------------------------------------------------------
# HTML renderers
# --------------------------------------------------------------------------

def render_header(box, running: bool = False) -> None:
    approval = st.session_state["approval"]
    if running:
        text, color = "INVESTIGATING", "#7DD3FC"
    elif not st.session_state["result"]:
        text, color = "AWAITING INCIDENT", "#8C97B8"
    elif approval == "APPROVED":
        text, color = "APPROVED", "#5BE3A0"
    elif approval == "REJECTED":
        text, color = "REJECTED", "#FF6B6B"
    else:
        text, color = "AWAITING HUMAN", "#FFB84D"
    box.markdown(
        '<div class="ap-head"><div class="ap-brand"><div class="ap-logo">AP</div><div>'
        '<div class="ap-title">DEVOPS AUTOPILOT</div>'
        '<div class="ap-sub">autonomous incident response / human-in-the-loop</div></div></div>'
        f'<div class="ap-chip" style="color:{color}"><span class="ap-dot" style="background:{color}"></span>'
        f'{h(text)}</div></div>',
        unsafe_allow_html=True)


def render_stage(box, key: str) -> None:
    index = next(i for i, (k, _, _) in enumerate(STAGES) if k == key) + 1
    _, name, sub = STAGES[index - 1]
    state = st.session_state["stage_states"][key]
    label, color, width = {
        "waiting": ("IDLE", "#8C97B8", "0%"),
        "running": ("WORKING...", "#7DD3FC", "55%"),
        "done": ("DONE", "#5BE3A0", "100%"),
        "failed": ("FAILED", "#FF6B6B", "100%"),
    }[state]
    glyph = {"done": "&#10003;", "failed": "!"}.get(state, str(index))
    bar_color = "#FF6B6B" if state == "failed" else "#4DE1C1"
    box.markdown(
        '<div class="ap-card" style="margin-bottom:0">'
        f'<div style="display:flex;align-items:center;gap:14px"><div class="ap-ring ap-{state}">{glyph}</div>'
        f'<div><div class="ap-h" style="margin:0">{h(name)}</div>'
        f'<div style="font:12px \'JetBrains Mono\',monospace;color:{color}">{label}</div></div></div>'
        f'<div class="ap-muted" style="margin-top:12px">{h(sub)}</div>'
        f'<div class="ap-bar"><div style="width:{width};background:{bar_color}"></div></div></div>',
        unsafe_allow_html=True)


def render_log(box) -> None:
    events = st.session_state["events"]
    if events:
        body = "".join(
            f'<div><span style="color:{TAG_COLORS.get(tag, "#C9D2EC")};font-weight:700">[{h(tag)}]</span> '
            f'<span class="ap-log-msg">{h(msg)}</span></div>'
            for tag, msg in events)
    else:
        body = '<div style="color:#8C97B8">$ waiting for an incident...</div>'
    box.markdown(
        '<div class="ap-term"><div class="ap-term-head"><span>LIVE TERMINAL</span>'
        f'<span>autopilot.log</span></div>{body}</div>',
        unsafe_allow_html=True)


def tile(label: str, value: str, color: str = "#E6EBFA", bar: float = None) -> str:
    bar_html = ""
    if bar is not None:
        bar_html = (f'<div class="ap-bar"><div style="width:{max(0, min(100, bar))}%;'
                    'background:#FF6B6B"></div></div>')
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
        lines.append(f'<span style="color:{color}">{escape(line or " ", quote=True).replace("$", "&#36;")}</span>')
    return "<br>".join(lines)


# --------------------------------------------------------------------------
# Sections
# --------------------------------------------------------------------------

def sidebar() -> None:
    st.sidebar.markdown('<div class="ap-h">Configuration</div>', unsafe_allow_html=True)
    groups = {
        "Groq (required to analyse)": ["GROQ_API_KEY"],
        "GitHub (source + PR)": ["GITHUB_TOKEN", "GITHUB_REPO_OWNER", "GITHUB_REPO_NAME"],
        "Slack (alerts)": ["SLACK_BOT_TOKEN", "SLACK_CHANNEL_ID"],
    }
    for title, names in groups.items():
        missing = agent_brain.get_missing_env(names)
        if missing:
            status = ("#FF6B6B", "Missing: " + ", ".join(missing))
        else:
            status = ("#5BE3A0", "Configured")
        st.sidebar.markdown(
            f'<div class="ap-card" style="padding:14px 16px;margin-bottom:10px">'
            f'<div class="ap-lbl" style="margin:0 0 6px">{h(title)}</div>'
            f'<div style="color:{status[0]};font:700 13px \'JetBrains Mono\',monospace">{h(status[1])}</div></div>',
            unsafe_allow_html=True)
    st.sidebar.markdown(
        '<div class="ap-muted"><b>Incident source:</b> Manual / Simulated<br>'
        '<b>Deployment:</b> Human-approved prototype workflow (no automatic deployment)</div>',
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
    rate_text = "n/a" if rate != rate else f"{rate:g}%"
    severity = report["severity"]
    risk = result["final_risk"]
    approval = st.session_state["approval"]
    approval_color = {"PENDING": "#FFB84D", "APPROVED": "#5BE3A0", "REJECTED": "#FF6B6B"}[approval]
    st.markdown(
        '<div class="ap-grid">'
        + tile("Error rate", rate_text, "#E6EBFA", None if rate != rate else rate)
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
            f'<div class="ap-lbl">Service / detected error</div>'
            f'<div class="ap-muted">{h(report["affected_service"])} / {h(report["detected_error"])}</div>'
            f'<div class="ap-lbl">Initial observation</div>'
            f'<div class="ap-text">{h(report["initial_observation"])}</div></div>'
            '<div class="ap-card"><div class="ap-h">Root cause</div>'
            f'<div class="ap-text">{h(diag["root_cause"])}</div>'
            f'<div style="margin-top:10px"><span class="ap-file">{h(diag["affected_file"])}</span>'
            f'<span class="ap-file">{h(diag["affected_function"])}</span></div>'
            f'<div class="ap-lbl">Why it happened</div><div class="ap-text">{h(diag["explanation"])}</div></div>',
            unsafe_allow_html=True)
    with right:
        diff_block = (f'<div class="ap-code">{diff_html(patch["diff"])}</div>'
                      if patch["diff"] else "")
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
            f'<div class="ap-text" style="color:#5BE3A0">PR #{h(pr["number"])} created ({h(kind)})</div>'
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
        st.markdown('<div class="ap-text" style="color:#5BE3A0">Approval request sent to Slack.</div>',
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
        "PENDING": ("LOCKED / PENDING", "#FFB84D",
                    "A human must approve before any merge or deployment."),
        "APPROVED": ("APPROVED", "#5BE3A0",
                     "Next step: review and merge the PR on GitHub yourself. "
                     "This app does not merge or deploy anything."),
        "REJECTED": ("REJECTED", "#FF6B6B", "Rejected. No further action will be taken."),
    }[state]
    st.markdown(
        '<div class="ap-h">Human gate</div>'
        f'<div style="font:700 13px \'JetBrains Mono\',monospace;color:{color}">{h(title)}</div>'
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
# Main page
# --------------------------------------------------------------------------

def main() -> None:
    init_state()
    st.markdown(THEME_CSS, unsafe_allow_html=True)
    sidebar()

    header_box = st.empty()
    left, right = st.columns(2, gap="large")

    with left:
        with st.container(border=True, key="card_intake"):
            st.markdown('<div class="ap-h">Incident intake</div>', unsafe_allow_html=True)
            c1, c2, c3 = st.columns([2, 1, 1])
            c1.text_input("Service", key="inp_service", placeholder="Payment API")
            c2.text_input("Error rate (%)", key="inp_error_rate", placeholder="38")
            c3.text_input("HTTP status", key="inp_http_status", placeholder="500")
            st.text_input("Error message", key="inp_error",
                          placeholder="AttributeError: ...")
            st.text_area("Stack trace", key="inp_trace", height=150)
            b1, b2 = st.columns(2)
            b1.button("Load sample incident", on_click=load_sample)
            analyze = b2.button("Analyze incident", type="primary")
            st.markdown('<div class="ap-muted">Incident source: Manual / Simulated</div>',
                        unsafe_allow_html=True)
    with right:
        log_box = st.empty()

    node_cols = st.columns(3, gap="large")
    boxes = {key: col.empty() for (key, _, _), col in zip(STAGES, node_cols)}

    def refresh(running: bool = False) -> None:
        render_header(header_box, running)
        render_log(log_box)
        for key, _, _ in STAGES:
            render_stage(boxes[key], key)

    refresh()

    if analyze:
        if agent_brain.get_missing_env(["GROQ_API_KEY"]):
            st.error("Missing configuration: GROQ_API_KEY. Add it to .env or Streamlit Secrets.")
        else:
            reset_incident()
            st.session_state["incident_id"] = agent_brain.generate_incident_id()
            incident = {
                "service": st.session_state["inp_service"],
                "error_rate": st.session_state["inp_error_rate"],
                "http_status": st.session_state["inp_http_status"],
                "error_message": st.session_state["inp_error"],
                "stack_trace": st.session_state["inp_trace"],
            }
            st.session_state["incident"] = incident
            add_event("system", f"Incident {st.session_state['incident_id']} received")
            refresh(running=True)

            def on_progress(stage: str, state: str) -> None:
                st.session_state["stage_states"][stage] = state
                event = STAGE_EVENTS.get((stage, state))
                if event:
                    add_event(*event)
                elif state == "failed":
                    add_event("system", f"{stage} agent failed")
                render_stage(boxes[stage], stage)
                render_log(log_box)

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
        st.markdown('<div class="ap-foot">prototype approval only / not a production-grade '
                    'authorization system (no user identity, no audit trail)</div>',
                    unsafe_allow_html=True)


main()
