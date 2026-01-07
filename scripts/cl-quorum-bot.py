#!/usr/bin/env python3
"""
Quorum Bot - Requires approvals from N distinct teams before merging a PR.
"""

import math
import os
import re
import sys
import time
import requests
from bs4 import BeautifulSoup

REQUIRED_APPROVAL_PERCENT = 51
BOT_USERNAME = "cl-quorum-bot"
REQUIRED_LABEL = "cl-quorum-bot"
PROTOCOL_GUILD_URL = "https://protocol-guild.readthedocs.io/en/latest/01-membership.html"


def calculate_required_approvals(num_teams):
    """Calculate required approvals (51% of teams, rounded up)."""
    return math.ceil(num_teams * REQUIRED_APPROVAL_PERCENT / 100)


def fetch_teams_from_protocol_guild():
    """
    Fetch consensus client team memberships from Protocol Guild.
    Dynamically discovers which teams are consensus clients.
    Returns dict: team_name -> list of GitHub usernames
    """
    response = requests.get(PROTOCOL_GUILD_URL, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    teams = {}

    # Find the table containing CONSENSUS CLIENTS
    consensus_table = None
    for table in soup.find_all("table"):
        if table.find("strong", string="CONSENSUS CLIENTS"):
            consensus_table = table
            break

    if not consensus_table:
        raise RuntimeError("CONSENSUS CLIENTS section not found - page structure may have changed")

    # Parse the table - look for CONSENSUS CLIENTS header, then collect teams until end
    in_consensus_section = False
    current_team = None

    for row in consensus_table.find_all("tr"):
        strong = row.find("strong")
        if not strong:
            # Member row - extract GitHub username if we're in a team
            if current_team:
                first_cell = row.find("td")
                if first_cell:
                    link = first_cell.find("a", href=True)
                    if link and "github.com/" in link["href"]:
                        match = re.search(r"github\.com/([^/]+)", link["href"])
                        if match:
                            username = match.group(1)
                            if username not in teams[current_team]:
                                teams[current_team].append(username)
            continue

        # This row has a <strong> tag - check what kind
        strong_text = strong.get_text().strip()
        cell_text = row.get_text().strip()

        # Check for section headers (all caps, no "contributors")
        if strong_text.isupper() and "contributors" not in cell_text.lower():
            if strong_text == "CONSENSUS CLIENTS":
                in_consensus_section = True
                current_team = None
            else:
                # Another major section (e.g., EXECUTION CLIENTS) - skip
                in_consensus_section = False
                current_team = None
            continue

        # Check for team headers (e.g., "Lighthouse (11 contributors)")
        if in_consensus_section and "contributors" in cell_text.lower():
            team_name = strong_text.lower()
            teams[team_name] = []
            current_team = team_name

    # Validate we found teams
    if not teams:
        raise RuntimeError("No consensus client teams found - page structure may have changed")

    for client, members in teams.items():
        if not members:
            raise RuntimeError(f"No members found for {client} - page structure may have changed")

    return teams


class APIError(Exception):
    """API request failed (token-safe exception)."""
    pass


def api_request(method, url, token, **kwargs):
    """
    Make a GitHub API request without exposing the token in tracebacks.

    Catches request exceptions and re-raises as APIError with sanitized message.
    """
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    try:
        response = requests.request(method, url, headers=headers, **kwargs)
        response.raise_for_status()
        return response
    except requests.RequestException as e:
        if e.response is not None:
            raise APIError(f"{method} {url} failed: {e.response.status_code}") from None
        raise APIError(f"{method} {url} failed: connection error") from None


def build_user_to_team_map(teams):
    """Build a reverse mapping from username to team name."""
    user_to_team = {}
    for team_name, members in teams.items():
        for username in members:
            user_to_team[username.lower()] = team_name
    return user_to_team


def get_pr(repo, pr_number, token):
    """Fetch PR details."""
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    response = api_request("GET", url, token)
    return response.json()


def get_reviews(repo, pr_number, token):
    """Fetch all reviews for a PR."""
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews"
    response = api_request("GET", url, token)
    return response.json()


def get_check_runs_status(repo, sha, token):
    """Get status of all check runs, excluding the quorum check itself."""
    url = f"https://api.github.com/repos/{repo}/commits/{sha}/check-runs"
    response = api_request("GET", url, token)
    check_runs = response.json()["check_runs"]
    if not check_runs:
        return "pending"
    for check in check_runs:
        # Skip ourself to avoid circular dependency
        if check["name"] == "quorum":
            continue
        if check["status"] != "completed":
            return "pending"
        if check["conclusion"] != "success":
            return "failure"
    return "success"


def get_team_review_states(reviews, user_to_team, pr_author):
    """
    Determine each team's review state based on the latest review from any team member.
    Reviews are processed in chronological order, so the last relevant review wins.
    The PR author is excluded - another team member must approve.
    Returns dict: team_name -> "APPROVED" | "CHANGES_REQUESTED"
    """
    team_states = {}
    pr_author_lower = pr_author.lower()
    for review in reviews:
        state = review["state"]
        if state in ("APPROVED", "CHANGES_REQUESTED"):
            username = review["user"]["login"].lower()
            # Skip the PR author - they can't approve their own PR for their team
            if username == pr_author_lower:
                continue
            team = user_to_team.get(username)
            if team:
                team_states[team] = state
    return team_states


def build_status_comment(team_states, teams, required_approvals):
    """Build the status comment markdown."""
    lines = [
        "This bot checks for approvals from consensus-layer client teams. "
        "Each team's status reflects the most recent review from any of its members. "
        f"Once {required_approvals}/{len(teams)} teams have approved, this PR will be automatically merged.",
        "",
        "| Team | Status |",
        "|------|:------:|",
    ]
    for team in sorted(teams):
        state = team_states.get(team)
        if state == "APPROVED":
            status = "✅"
        elif state == "CHANGES_REQUESTED":
            status = "❌"
        else:
            status = "❓"
        lines.append(f"| {team.capitalize()} | {status} |")
    return "\n".join(lines)


def find_bot_comment(repo, pr_number, token):
    """Find existing bot comment on the PR."""
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    response = api_request("GET", url, token)
    for comment in response.json():
        if comment["user"]["login"] == BOT_USERNAME:
            return comment["id"]
    return None


def post_or_update_comment(repo, pr_number, token, body):
    """Post a new comment or update existing one."""
    existing_id = find_bot_comment(repo, pr_number, token)
    if existing_id:
        url = f"https://api.github.com/repos/{repo}/issues/comments/{existing_id}"
        response = api_request("PATCH", url, token, json={"body": body})
    else:
        url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
        response = api_request("POST", url, token, json={"body": body})
    return response.json()


def delete_bot_comment(repo, pr_number, token):
    """Delete the bot's comment if it exists."""
    existing_id = find_bot_comment(repo, pr_number, token)
    if existing_id:
        url = f"https://api.github.com/repos/{repo}/issues/comments/{existing_id}"
        api_request("DELETE", url, token)
        return True
    return False


def merge_pr(repo, pr_number, token):
    """Squash merge the PR."""
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/merge"
    response = api_request("PUT", url, token, json={"merge_method": "squash"})
    return response.json()


def main():
    # Get environment variables
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    pr_number = os.environ.get("PR_NUMBER")

    if not all([token, repo, pr_number]):
        print("Missing required environment variables")
        print(f"  GITHUB_TOKEN: {'set' if token else 'missing'}")
        print(f"  GITHUB_REPOSITORY: {repo or 'missing'}")
        print(f"  PR_NUMBER: {pr_number or 'missing'}")
        sys.exit(1)

    # Fetch team memberships from Protocol Guild
    print("Fetching team memberships from Protocol Guild...")
    teams = fetch_teams_from_protocol_guild()
    for team, members in teams.items():
        print(f"  {team}: {len(members)} members")

    required_approvals = calculate_required_approvals(len(teams))
    user_to_team = build_user_to_team_map(teams)

    print(f"Processing PR #{pr_number} in {repo}")
    print(f"Required approvals: {required_approvals}/{len(teams)} teams ({REQUIRED_APPROVAL_PERCENT}%)")

    # Fetch PR details
    pr = get_pr(repo, pr_number, token)
    pr_author = pr["user"]["login"]
    print(f"PR author: {pr_author}")

    # Check for required label
    pr_labels = [label["name"] for label in pr.get("labels", [])]
    if REQUIRED_LABEL not in pr_labels:
        print(f"Label '{REQUIRED_LABEL}' not found. Skipping.")
        if delete_bot_comment(repo, pr_number, token):
            print("Deleted bot comment.")
        return

    # Check PR state
    if pr["state"] != "open":
        print(f"PR is not open (state: {pr['state']}).")
        sys.exit(1)
    if pr.get("draft", False):
        print("PR is a draft.")
        sys.exit(1)

    # Fetch and process reviews (excluding PR author)
    reviews = get_reviews(repo, pr_number, token)
    team_states = get_team_review_states(reviews, user_to_team, pr_author)

    approved_teams = [t for t, s in team_states.items() if s == "APPROVED"]
    print(f"Approving teams: {approved_teams}")

    # Post status comment
    comment_body = build_status_comment(team_states, teams, required_approvals)
    post_or_update_comment(repo, pr_number, token, comment_body)
    print("Status comment updated")

    # Check if we have quorum
    if len(approved_teams) < required_approvals:
        print(
            f"Quorum not reached ({len(approved_teams)}/{required_approvals}). "
            f"Waiting for more approvals."
        )
        sys.exit(1)

    print(f"Quorum reached ({len(approved_teams)}/{required_approvals})!")

    # Wait for status checks to pass (poll for up to 1 hour)
    head_sha = pr["head"]["sha"]

    max_attempts = 60  # 60 attempts * 60 seconds = 1 hour
    poll_interval = 60  # seconds

    for attempt in range(max_attempts):
        status = get_check_runs_status(repo, head_sha, token)
        print(f"Status checks: {status} (attempt {attempt + 1}/{max_attempts})")

        if status == "success":
            print("Merging...")
            merge_pr(repo, pr_number, token)
            print("PR merged successfully!")
            return
        elif status == "pending":
            print(f"Waiting {poll_interval}s for status checks...")
            time.sleep(poll_interval)
        else:
            print(f"Status checks failed ({status}). Not merging.")
            sys.exit(1)

    print("Timed out waiting for status checks.")
    sys.exit(1)


if __name__ == "__main__":
    main()
