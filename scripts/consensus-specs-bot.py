#!/usr/bin/env python3
"""
Consensus Specs Bot - Requires at least one maintainer approval plus one approval from
each labeled group (domain/EIP) before merging a PR.
"""

import os
import sys
import time
import requests
import yaml

BOT_USERNAME = "consensus-specs-bot"
MAINTAINERS = "maintainers"
REVIEWERS_FILE = os.path.join(os.path.dirname(__file__), "..", "reviewers.yml")


def load_reviewers():
    """
    Load all reviewer groups from YAML file.
    Returns dict: label -> list of usernames
    """
    with open(REVIEWERS_FILE, "r") as f:
        data = yaml.safe_load(f)

    if not data:
        raise RuntimeError(f"No reviewers found in {REVIEWERS_FILE}")

    return data


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


def get_check_runs_status(repo, sha, token, self_check_name):
    """Get status of all check runs, excluding our own check."""
    url = f"https://api.github.com/repos/{repo}/commits/{sha}/check-runs"
    response = api_request("GET", url, token)
    check_runs = response.json()["check_runs"]
    if not check_runs:
        return "pending"
    for check in check_runs:
        # Skip ourself to avoid circular dependency
        if check["name"] == self_check_name:
            continue
        if check["status"] != "completed":
            return "pending"
        if check["conclusion"] != "success":
            return "failure"
    return "success"


def get_reviewer_states(reviews, reviewers, pr_author):
    """
    Collect each reviewer's most recent review.
    Returns dict: username -> "APPROVED" | "CHANGES_REQUESTED"
    """
    reviewer_set = {r.lower() for r in reviewers}
    reviewer_states = {}
    pr_author_lower = pr_author.lower()
    for review in reviews:
        state = review["state"]
        if state in ("APPROVED", "CHANGES_REQUESTED"):
            username = review["user"]["login"]
            if username.lower() == pr_author_lower:
                continue
            if username.lower() in reviewer_set:
                reviewer_states[username] = state
    return reviewer_states


def process_reviewers(reviews, reviewers, pr_author):
    """
    Process reviewers and return results.
    Returns (reviewer_states, reviewers, approved_count)
    """
    reviewer_states = get_reviewer_states(reviews, reviewers, pr_author)
    approved_count = sum(1 for s in reviewer_states.values() if s == "APPROVED")
    return reviewer_states, reviewers, approved_count


def build_table(reviewer_states, reviewers):
    """Build markdown table rows for reviewers."""
    rows = []
    for reviewer in sorted(reviewers, key=str.lower):
        review_state = reviewer_states.get(reviewer)
        if review_state is None:
            # Check case-insensitive
            for user, state in reviewer_states.items():
                if user.lower() == reviewer.lower():
                    review_state = state
                    reviewer = user  # Use the actual username from review
                    break

        if review_state == "APPROVED":
            status = "✅"
        elif review_state == "CHANGES_REQUESTED":
            status = "❌"
        else:
            status = "❓"

        rows.append(f"| @{reviewer} | {status} |")

    return "\n".join(rows)


def build_section(label, reviewers, reviews, pr_author):
    """Build a comment section for a single label."""
    reviewer_states, reviewers, approved = process_reviewers(
        reviews, reviewers, pr_author
    )
    table = build_table(reviewer_states, reviewers)

    header = f"### `{label}`\n\n"
    table_header = "| Reviewer | Status |\n|----------|:------:|"

    return f"{header}{table_header}\n{table}", approved


def build_status_comment(active_labels, all_reviewers, reviews, pr_author):
    """Build the full status comment with all active label sections."""
    sections = []
    results = {}

    # Process maintainers first, then other labels alphabetically
    ordered_labels = []
    if MAINTAINERS in active_labels:
        ordered_labels.append(MAINTAINERS)
    for label in sorted(active_labels):
        if label != MAINTAINERS:
            ordered_labels.append(label)

    for label in ordered_labels:
        reviewers = all_reviewers.get(label)
        if not reviewers:
            continue

        section, approved = build_section(
            label, reviewers, reviews, pr_author
        )
        sections.append(section)
        results[label] = {"approved": approved}

    note = (
        "This PR has been flagged for review by subject matter experts. "
        "It will be automatically merged once at least one maintainer approves, "
        "at least one reviewer from each labeled group approves, "
        "all CI checks pass, and the branch is up-to-date with the base branch."
    )

    body = f"{note}\n\n" + "\n\n---\n\n".join(sections)
    return body, results


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
    check_name = os.environ.get("CHECK_NAME", "reviewers")

    if not all([token, repo, pr_number]):
        print("Missing required environment variables")
        print(f"  GITHUB_TOKEN: {'set' if token else 'missing'}")
        print(f"  GITHUB_REPOSITORY: {repo or 'missing'}")
        print(f"  PR_NUMBER: {pr_number or 'missing'}")
        sys.exit(1)

    # Load all reviewers from YAML file
    print("Loading reviewers...")
    all_reviewers = load_reviewers()
    for label, reviewers in all_reviewers.items():
        count = len(reviewers) if reviewers else 0
        print(f"  {label}: {count} reviewers")

    print(f"Processing PR #{pr_number} in {repo}")

    # Fetch PR details
    pr = get_pr(repo, pr_number, token)
    pr_author = pr["user"]["login"]
    print(f"PR author: {pr_author}")

    # Find labels that match reviewer groups in reviewers.yml
    pr_labels = [label["name"] for label in pr.get("labels", [])]
    active_labels = []
    for label in pr_labels:
        if label in all_reviewers:
            reviewers = all_reviewers[label]
            # Skip empty groups
            if reviewers and len(reviewers) > 0:
                active_labels.append(label)
            else:
                print(f"Warning: '{label}' has no reviewers, skipping")

    if not active_labels:
        print("No reviewer labels found. Skipping.")
        if delete_bot_comment(repo, pr_number, token):
            print("Deleted bot comment.")
        return

    # Always require maintainer approval
    if MAINTAINERS not in active_labels:
        active_labels.append(MAINTAINERS)

    print(f"Active labels: {active_labels}")

    # Check PR state
    pr_state = pr["state"]
    if pr_state == "merged":
        print("PR is already merged.")
        sys.exit(1)
    if pr.get("draft", False):
        print("PR is a draft.")
        sys.exit(1)
    if pr.get("mergeable_state") == "behind":
        print("PR is out of date with base branch. Please update before merging.")
        sys.exit(1)

    # Fetch reviews
    reviews = get_reviews(repo, pr_number, token)

    # Build status comment and get results
    comment_body, results = build_status_comment(
        active_labels, all_reviewers, reviews, pr_author
    )
    post_or_update_comment(repo, pr_number, token, comment_body)
    print("Status comment updated")

    # Check results across all labels
    all_approved = True

    for label, result in results.items():
        approved = result["approved"]
        print(f"  {label}: {approved} approval(s)")

        if approved < 1:
            all_approved = False

    # Check if all labels have at least one approval
    if not all_approved:
        print("Waiting for approvals.")
        sys.exit(1)

    print("All labels have at least one approval!")

    # Wait for status checks to pass (poll for up to 1 hour)
    head_sha = pr["head"]["sha"]

    max_attempts = 60  # 60 attempts * 60 seconds = 1 hour
    poll_interval = 60  # seconds

    for attempt in range(max_attempts):
        status = get_check_runs_status(repo, head_sha, token, check_name)
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
