"""
github_service.py - GitHub operations for DevOps Autopilot.

The AI decides WHAT to change. This module only handles HOW to do it on GitHub.

Safety rules enforced here:
  * Changes only ever go to a dedicated branch (devops-autopilot/fix-<id>).
  * We never write to the default branch (main/master).
  * We open a Pull Request; we never merge it.
  * Sensitive paths (.env, keys, workflows) cannot be read or modified.

No Streamlit code lives in this file.
"""

import logging
import os
import re
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from github import Auth, Github, GithubException

load_dotenv()

logger = logging.getLogger("devops_autopilot.github")

BRANCH_PREFIX = "devops-autopilot/"
MAX_FILE_BYTES = 200_000
PROTECTED_BRANCHES = {"main", "master"}
BLOCKED_PATH_PATTERNS = (
    r"(^|/)\.env(\..*)?$",
    r"(^|/)\.git/",
    r"(^|/)\.github/",
    r"\.(pem|key|p12|pfx)$",
    r"(^|/)secrets?(\.|/)",
    r"(^|/)id_rsa",
)


class GitHubServiceError(Exception):
    """An error whose message is safe to show to the user (never contains secrets)."""


def _describe(exc: GithubException) -> str:
    """Translate a GitHub API error into a safe, friendly message."""
    status = getattr(exc, "status", None)
    if status == 401:
        return "GitHub authentication failed. Check GITHUB_TOKEN."
    if status == 403:
        return "GitHub denied access (missing permission or rate limit)."
    if status == 404:
        return "Repository or file not found, or the token cannot access it."
    if status == 422:
        return "GitHub rejected the request (for example, the branch or PR already exists)."
    return f"GitHub API error (status {status})."


def validate_repo_path(file_path: str) -> str:
    """Reject absolute paths, path traversal and sensitive files."""
    path = (file_path or "").strip().replace("\\", "/")
    if not path or path.startswith("/") or ".." in path.split("/"):
        raise GitHubServiceError("Invalid file path.")
    for pattern in BLOCKED_PATH_PATTERNS:
        if re.search(pattern, path, flags=re.IGNORECASE):
            raise GitHubServiceError("Access to this file path is blocked for safety.")
    return path


def get_repository():
    """Authenticate with the token from the environment and return the repo."""
    token = (os.getenv("GITHUB_TOKEN") or "").strip()
    owner = (os.getenv("GITHUB_REPO_OWNER") or "").strip()
    name = (os.getenv("GITHUB_REPO_NAME") or "").strip()
    missing = [
        var for var, val in (
            ("GITHUB_TOKEN", token),
            ("GITHUB_REPO_OWNER", owner),
            ("GITHUB_REPO_NAME", name),
        ) if not val or val.startswith("your_")
    ]
    if missing:
        raise GitHubServiceError("Missing GitHub configuration: " + ", ".join(missing))
    try:
        client = Github(auth=Auth.Token(token))
        repo = client.get_repo(f"{owner}/{name}")
    except GithubException as exc:
        raise GitHubServiceError(_describe(exc)) from None
    logger.info("GitHub service initialized")
    return repo


def get_file_content(file_path: str, repo=None, ref: Optional[str] = None) -> Optional[str]:
    """Return a text file's content, or None if it does not exist."""
    path = validate_repo_path(file_path)
    repo = repo or get_repository()
    try:
        item = repo.get_contents(path, ref=ref) if ref else repo.get_contents(path)
    except GithubException as exc:
        if exc.status == 404:
            return None
        raise GitHubServiceError(_describe(exc)) from None
    if isinstance(item, list):  # it is a directory
        return None
    if item.size > MAX_FILE_BYTES:
        raise GitHubServiceError("File is too large to analyse.")
    try:
        return item.decoded_content.decode("utf-8")
    except UnicodeDecodeError:
        raise GitHubServiceError("File is not a UTF-8 text file.") from None


def create_branch(repo, branch_name: str) -> str:
    """Create a new branch from the default branch; returns the final name."""
    if not branch_name.startswith(BRANCH_PREFIX):
        raise GitHubServiceError("Branch name must start with " + BRANCH_PREFIX)
    try:
        base_sha = repo.get_branch(repo.default_branch).commit.sha
        candidate, counter = branch_name, 1
        while True:  # avoid clashing with an existing branch
            try:
                repo.get_branch(candidate)
                counter += 1
                candidate = f"{branch_name}-{counter}"
            except GithubException as exc:
                if exc.status == 404:
                    break
                raise
        repo.create_git_ref(ref=f"refs/heads/{candidate}", sha=base_sha)
    except GithubException as exc:
        raise GitHubServiceError(_describe(exc)) from None
    logger.info("Created branch %s", candidate)
    return candidate


def create_file_change(repo, branch: str, file_path: str, content: str, message: str) -> None:
    """Create or update one file on a non-default branch."""
    path = validate_repo_path(file_path)
    if branch in PROTECTED_BRANCHES or branch == repo.default_branch:
        raise GitHubServiceError("Refusing to write to the default branch.")
    try:
        try:
            existing = repo.get_contents(path, ref=branch)
            repo.update_file(path, message, content, existing.sha, branch=branch)
        except GithubException as exc:
            if exc.status != 404:
                raise
            repo.create_file(path, message, content, branch=branch)
    except GithubException as exc:
        raise GitHubServiceError(_describe(exc)) from None


def create_pull_request(repo, branch: str, title: str, body: str) -> Dict[str, Any]:
    """Open a (draft if possible) Pull Request. Never merges."""
    try:
        try:
            pr = repo.create_pull(title=title, body=body, head=branch,
                                  base=repo.default_branch, draft=True)
        except GithubException as exc:
            if exc.status != 422:
                raise
            # Some private repos/plans do not support draft PRs.
            pr = repo.create_pull(title=title, body=body, head=branch,
                                  base=repo.default_branch, draft=False)
    except GithubException as exc:
        raise GitHubServiceError(_describe(exc)) from None
    logger.info("Pull request #%s created", pr.number)
    return {"url": pr.html_url, "number": pr.number, "draft": bool(pr.draft)}


def build_pr_body(incident_id: str, report: Dict[str, Any], diagnosis: Dict[str, Any],
                  guard: Dict[str, Any], patch: Dict[str, Any], risk_level: str) -> str:
    """Compose the Pull Request description."""
    tests = "\n".join(f"- {t}" for t in diagnosis.get("test_plan", [])) or "- (none suggested)"
    return (
        f"## DevOps Autopilot proposed fix - {incident_id}\n\n"
        "> **AI-generated. Validation: NOT RUN. Human review is required before merging.**\n\n"
        f"**Incident:** {report.get('incident_summary')}\n\n"
        f"**Severity:** {report.get('severity')}  |  **Risk:** {risk_level}\n\n"
        f"**Root cause:** {diagnosis.get('root_cause')}\n\n"
        f"**Affected file:** `{diagnosis.get('affected_file')}`  "
        f"(function: `{diagnosis.get('affected_function')}`)\n\n"
        f"**Proposed fix:** {diagnosis.get('proposed_fix')}\n\n"
        f"**Guard review:** {guard.get('risk_reasoning')}\n\n"
        f"### Suggested tests\n{tests}\n\n"
        f"### Diff\n```diff\n{patch.get('diff') or '(no diff available)'}\n```\n"
    )


def create_fix_pull_request(incident_id: str, title: str, body: str,
                            file_path: Optional[str] = None,
                            new_content: Optional[str] = None,
                            proposal_markdown: str = "") -> Dict[str, Any]:
    """
    Branch -> commit -> Pull Request.

    If we have a verified code change (file_path + new_content) we commit it.
    Otherwise we commit a Markdown proposal so a human can still review it.
    """
    safe_id = re.sub(r"[^A-Za-z0-9._-]", "-", incident_id)
    repo = get_repository()
    branch = create_branch(repo, f"{BRANCH_PREFIX}fix-{safe_id}")
    message = f"[DevOps Autopilot] Proposed fix for {safe_id}"

    if file_path and new_content is not None:
        create_file_change(repo, branch, file_path, new_content, message)
        mode = "code_change"
    else:
        create_file_change(repo, branch, f"devops-autopilot-proposals/{safe_id}.md",
                           proposal_markdown or body, message)
        mode = "proposal_only"

    pr = create_pull_request(repo, branch, title, body)
    pr.update({"branch": branch, "mode": mode})
    return pr
