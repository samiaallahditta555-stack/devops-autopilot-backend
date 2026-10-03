# DevOps Autopilot

**Autonomous Agentic Incident Response & Infrastructure Guard** - a hackathon prototype that behaves like a simplified Site Reliability Engineer (SRE), with a human always in the loop.

## Description

You give it a production incident (error message, stack trace, HTTP status). Three AI agents analyse it, find the probable root cause, propose a minimal code fix, assess the risk, open a GitHub Pull Request and ask a human for approval through Slack and the dashboard.

## Problem

- **Production incidents** are stressful and costly.
- **High MTTR** (mean time to resolve): finding the bad line of code takes hours.
- **On-call fatigue**: engineers get paged at night for repetitive bugs.
- **Manual debugging**: reading logs and stack traces is slow and error-prone.
- **Infrastructure cost spikes**: long outages and retry storms burn money.

## Solution: a three-agent crew (CrewAI + Groq)

| Agent | Job |
|---|---|
| **Monitor Agent** | Reads the incident, classifies the error and severity, writes an incident report. |
| **Diagnoser & Fixer** | Reads the failing file from GitHub, finds the root cause, proposes a minimal patch and tests. |
| **Guard & Orchestrator** | Reviews the fix, assigns risk, prepares the approval request. Never approves anything itself. |

## Architecture

```text
Incident
   ↓
Monitor Agent
   ↓
Diagnoser & Fixer
   ↓
Guard & Orchestrator
   ↓
Human Approval
   ↓
GitHub PR
   ↓
Deployment (manual, outside this prototype)
```

In the dashboard you create the PR and send the Slack alert with buttons, then approve or reject.

## Technology Stack

```text
Python, CrewAI, Groq, GitHub API (PyGithub), Slack (slack_sdk), Streamlit, Git, GitHub
```

## Project Structure

```text
devops-autopilot/
├── .env                 Local secrets (placeholders only, never committed)
├── .gitignore           Keeps .env, venvs, caches and logs out of Git
├── requirements.txt     Minimal dependencies
├── README.md            This file
└── app/
    ├── main.py            Streamlit UI and entry point
    ├── agent_brain.py     CrewAI agents, prompts, workflow, parsing
    ├── github_service.py  Branch / commit / Pull Request operations
    └── slack_service.py   Slack alert and approval request
```

## Installation

```bash
git clone <repository-url>
cd devops-autopilot
python -m venv venv
```

Activate it (Windows): `venv\Scripts\activate`  |  (macOS/Linux): `source venv/bin/activate`

```bash
pip install -r requirements.txt
```

Use Python 3.10 - 3.13.

## Environment Variables

Edit `.env` locally (never commit it):

```env
GROQ_API_KEY=
GROQ_MODEL=
GITHUB_TOKEN=
GITHUB_REPO_OWNER=
GITHUB_REPO_NAME=
SLACK_BOT_TOKEN=
SLACK_CHANNEL_ID=
```

- `GROQ_MODEL` is optional (defaults to `llama-3.3-70b-versatile`).
- GitHub token: a fine-grained token limited to **one repository** with *Contents: read/write* and *Pull requests: read/write*.
- Slack: create an app, add the `chat:write` scope, install it, copy the bot token, then `/invite @your-bot` in the channel.

## Run Locally

```bash
streamlit run app/main.py
```

## GitHub Deployment

```bash
git init
git add .
git status        # confirm .env is NOT listed
git commit -m "Initial DevOps Autopilot backend"
git branch -M main
git remote add origin <repository-url>
git push -u origin main
```

## Streamlit Deployment

1. Push the repo to GitHub.
2. On Streamlit Community Cloud choose **New app**, select the repo, branch `main`, main file `app/main.py`.
3. In **Advanced settings** pick Python 3.11 and paste your secrets (below). Do not commit `.env`.

```toml
GROQ_API_KEY = "..."
GROQ_MODEL = "..."
GITHUB_TOKEN = "..."
GITHUB_REPO_OWNER = "..."
GITHUB_REPO_NAME = "..."
SLACK_BOT_TOKEN = "..."
SLACK_CHANNEL_ID = "..."
```

Streamlit exposes top-level secrets as environment variables, so the code reads them with `os.getenv`.

## Security Warning

> Never commit `.env`, API keys, GitHub tokens, Slack tokens, passwords, or other secrets to GitHub.

Built-in safeguards: no hardcoded credentials, secrets redacted from incident text and errors, branch-only changes (never `main`), PRs are never merged, sensitive file paths are blocked, agents cannot run shell commands.

## Current Prototype Limitations

- Monitoring is manual/simulated; there is no live log or Kubernetes integration.
- Deployment is not automated. "Approved" only records a decision.
- Streamlit approval is a prototype: no user identity or audit trail.
- Real production deployment requires proper authentication and authorization.
- AI-generated patches can be wrong and require human review.
- Validation is always **NOT RUN**; automated testing needs an isolated execution environment.
- A code change is committed to the PR only when the agent's snippet matches the real file exactly once; otherwise the PR contains a Markdown proposal.
- Groq is accessed through CrewAI's LiteLLM layer, so no separate Groq SDK is installed.

## Demo Tip

Click **Load Sample Incident**. For a code-change PR, your GitHub repo should contain `services/customer_service.py` with a `process_customer` function that uses `customer.email`.
