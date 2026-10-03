"""
main.py - Streamlit dashboard for DevOps Autopilot (UI only).

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

import streamlit as st  # noqa: E402

st.set_page_config(page_title="DevOps Autopilot", page_icon="🛠️", layout="wide")

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("devops_autopilot.main")

import agent_brain  # noqa: E402
import github_service  # noqa: E402
import slack_service  # noqa: E402

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
    ("monitor", "Monitor Agent", "Incident detected"),
    ("diagnoser", "Diagnoser & Fixer", "Root cause identified"),
    ("guard", "Guard & Orchestrator", "Risk assessed - awaiting human approval"),
]
STAGE_ICONS = {"waiting": "⏳ Waiting", "running": "🔄 Running...", "failed": "❌ Failed"}


def init_state() -> None:
    defaults = {
        "result": None, "incident_id": None, "pr_info": None, "slack_info": None,
        "approval": "PENDING",
        "stage_states": {key: "waiting" for key, _, _ in STAGES},
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)
    for key in SAMPLE_INCIDENT:
        st.session_state.setdefault(key, "")


def load_sample() -> None:
    for key, value in SAMPLE_INCIDENT.items():
        st.session_state[key] = value


def render_stage(box, key: str) -> None:
    label, done_text = next((l, d) for k, l, d in STAGES if k == key)
    state = st.session_state["stage_states"][key]
    status = f"✅ {done_text}" if state == "done" else STAGE_ICONS[state]
    box.markdown(f"**{label}**  \n{status}")


def sidebar() -> None:
    st.sidebar.header("Configuration")
    groups = {
        "Groq (required to analyse)": ["GROQ_API_KEY"],
        "GitHub (for source + PR)": ["GITHUB_TOKEN", "GITHUB_REPO_OWNER", "GITHUB_REPO_NAME"],
        "Slack (for alerts)": ["SLACK_BOT_TOKEN", "SLACK_CHANNEL_ID"],
    }
    for title, names in groups.items():
        missing = agent_brain.get_missing_env(names)
        st.sidebar.markdown(f"**{title}**")
        if missing:
            st.sidebar.markdown("❌ Missing: " + ", ".join(f"`{m}`" for m in missing))
        else:
            st.sidebar.markdown("✅ Configured")
    st.sidebar.divider()
    st.sidebar.markdown(
        "**Incident source:** Manual / Simulated  \n"
        "**Deployment:** Human-approved prototype workflow (no automatic deployment)"
    )


def show_results(result: dict) -> None:
    report, diag = result["incident_report"], result["diagnosis"]
    guard, patch = result["guard_review"], result["patch"]

    st.subheader("Incident Summary")
    c1, c2, c3 = st.columns(3)
    c1.metric("Severity", report["severity"])
    c2.metric("Risk Level", result["final_risk"])
    c3.metric("Validation", result["validation_status"])
    st.write(guard["incident_summary"])
    st.caption(f"Service: {report['affected_service']}  |  Detected error: {report['detected_error']}")
    st.write(f"**Initial observation:** {report['initial_observation']}")

    st.subheader("Root Cause")
    st.write(diag["root_cause"])
    st.caption(f"File: `{diag['affected_file']}`  |  Function: `{diag['affected_function']}`")
    st.write(diag["explanation"])

    st.subheader("Proposed Fix")
    st.write(diag["proposed_fix"])
    if patch["diff"]:
        st.code(patch["diff"], language="diff")
    st.caption(f"Patch status: {patch['reason']}")

    st.subheader("Test / Validation")
    st.warning("Validation: NOT RUN. No tests were executed; the items below are only recommendations.")
    for test in diag["test_plan"]:
        st.markdown(f"- {test}")

    st.subheader("Guard Review")
    st.write(f"**Risk reasoning:** {guard['risk_reasoning']}")
    st.write(f"**Recommendation:** {guard['recommendation']}")
    for concern in guard["concerns"]:
        st.markdown(f"- ⚠️ {concern}")


def pr_section(result: dict) -> None:
    st.subheader("GitHub Pull Request")
    pr = st.session_state["pr_info"]
    if pr:
        kind = "code change" if pr["mode"] == "code_change" else "proposal document only"
        st.success(f"PR #{pr['number']} created ({kind}, branch `{pr['branch']}`)")
        st.markdown(f"[Open pull request]({pr['url']})")
        return
    st.caption("Creates a branch and a Pull Request. Nothing is merged or pushed to main.")
    if st.button("Create GitHub Pull Request"):
        report, diag = result["incident_report"], result["diagnosis"]
        patch = result["patch"]
        body = github_service.build_pr_body(st.session_state["incident_id"], report, diag,
                                            result["guard_review"], patch, result["final_risk"])
        try:
            with st.spinner("Creating pull request..."):
                st.session_state["pr_info"] = github_service.create_fix_pull_request(
                    incident_id=st.session_state["incident_id"],
                    title=f"[DevOps Autopilot] {report['incident_summary'][:80]}",
                    body=body,
                    file_path=patch["file_path"] if patch["applied"] else None,
                    new_content=patch["new_content"] if patch["applied"] else None,
                    proposal_markdown=body,
                )
            st.rerun()
        except github_service.GitHubServiceError as exc:
            st.error(str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.error("PR creation failed: %s", type(exc).__name__)
            st.error("An unexpected error occurred while creating the pull request.")


def slack_section(result: dict) -> None:
    st.subheader("Slack Notification")
    info = st.session_state["slack_info"]
    if info:
        st.success("Approval request sent to Slack.")
        return
    if st.button("Send Slack approval request"):
        try:
            with st.spinner("Sending to Slack..."):
                st.session_state["slack_info"] = slack_service.send_incident_alert(
                    incident_id=st.session_state["incident_id"],
                    report=result["incident_report"], diagnosis=result["diagnosis"],
                    risk_level=result["final_risk"],
                    validation_status=result["validation_status"],
                    pr_info=st.session_state["pr_info"],
                    approval_status=st.session_state["approval"],
                )
            st.rerun()
        except slack_service.SlackServiceError as exc:
            st.error(str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.error("Slack failed: %s", type(exc).__name__)
            st.error("An unexpected error occurred while contacting Slack.")


def approval_section() -> None:
    st.subheader("Human Approval")
    state = st.session_state["approval"]
    st.markdown(f"**Approval status: `{state}`**")
    if state == "PENDING":
        col1, col2, _ = st.columns([1, 1, 4])
        if col1.button("Approve Fix", type="primary"):
            st.session_state["approval"] = "APPROVED"
            logger.info("Fix approved by reviewer")
            st.rerun()
        if col2.button("Reject Fix"):
            st.session_state["approval"] = "REJECTED"
            logger.info("Fix rejected by reviewer")
            st.rerun()
    elif state == "APPROVED":
        st.success("Approved. Next step: review and merge the PR on GitHub yourself. "
                   "This app does not merge or deploy anything.")
    else:
        st.info("Rejected. No further action will be taken.")
    st.caption("Prototype HITL only: these buttons are NOT a production-grade authorization "
               "system (no user identity, no audit trail).")


def main() -> None:
    init_state()
    sidebar()

    st.title("🛠️ DevOps Autopilot")
    st.caption("Autonomous Incident Response - prototype with human-in-the-loop approval")

    st.header("Incident Input")
    st.button("Load Sample Incident", on_click=load_sample)
    col1, col2, col3 = st.columns(3)
    col1.text_input("Service", key="inp_service", placeholder="Payment API")
    col2.text_input("Error rate (%)", key="inp_error_rate", placeholder="38")
    col3.text_input("HTTP status", key="inp_http_status", placeholder="500")
    st.text_input("Error message", key="inp_error")
    st.text_area("Stack trace", key="inp_trace", height=180)

    analyze = st.button("Analyze Incident", type="primary")

    st.divider()
    cols = st.columns(3)
    boxes = {key: col.empty() for (key, _, _), col in zip(STAGES, cols)}

    if analyze:
        missing = agent_brain.get_missing_env(["GROQ_API_KEY"])
        if missing:
            st.error("Missing configuration: GROQ_API_KEY. Add it to .env or Streamlit Secrets.")
        else:
            st.session_state.update(result=None, pr_info=None, slack_info=None, approval="PENDING",
                                    incident_id=agent_brain.generate_incident_id(),
                                    stage_states={k: "waiting" for k, _, _ in STAGES})

            def on_progress(stage: str, state: str) -> None:
                st.session_state["stage_states"][stage] = state
                render_stage(boxes[stage], stage)

            incident = {
                "service": st.session_state["inp_service"],
                "error_rate": st.session_state["inp_error_rate"],
                "http_status": st.session_state["inp_http_status"],
                "error_message": st.session_state["inp_error"],
                "stack_trace": st.session_state["inp_trace"],
            }
            try:
                with st.spinner("Agents are working..."):
                    outcome = agent_brain.run_incident_response(incident, on_progress)
            except Exception as exc:  # noqa: BLE001 - last-resort guard
                logger.error("Unexpected failure: %s", type(exc).__name__)
                outcome = {"ok": False, "error": "An error occurred while processing the incident."}
            if outcome["ok"]:
                st.session_state["result"] = outcome
            else:
                st.error(outcome["error"])

    for key, _, _ in STAGES:
        render_stage(boxes[key], key)

    result = st.session_state["result"]
    if result:
        for warning in result["warnings"]:
            st.warning(warning)
        st.divider()
        show_results(result)
        st.divider()
        pr_section(result)
        slack_section(result)
        st.divider()
        approval_section()


main()
