"""Refresh the generated README section from public, merged pull requests."""

import html
import json
import os
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

USERNAME = "Jarvis636431"
LIMIT = 6
START = "<!-- contributions:start -->"
END = "<!-- contributions:end -->"
QUERY = f"is:pr is:merged author:{USERNAME} is:public -user:{USERNAME}"
README = Path(__file__).resolve().parents[1] / "README.md"


def fetch_contributions():
    params = urlencode({"q": QUERY, "sort": "created", "order": "desc", "per_page": LIMIT})
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-contributions"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    request = Request("https://api.github.com/search/issues?" + params, headers=headers)
    with urlopen(request, timeout=30) as response:
        data = json.load(response)
    if data.get("incomplete_results") or not isinstance(data.get("items"), list):
        raise ValueError("GitHub returned incomplete or invalid search results")
    return data["items"]


def escape_text(value):
    value = html.escape(" ".join(value.split()), quote=True)
    return re.sub(r"([\\`*_[\]{}|])", r"\\\1", value)


def display_title(title):
    # Remove conventional commit metadata to make the profile easier to scan.
    title = re.sub(
        r"^(?:fix|feat|docs|chore|refactor|perf|test|build|ci|style|revert)"
        r"(?:\([^)]*\))?!?:\s*",
        "",
        title,
        flags=re.IGNORECASE,
    ).strip()
    return title[:1].upper() + title[1:]


def render_contributions(items):
    projects = {}
    for item in items[:LIMIT]:
        if not item.get("pull_request", {}).get("merged_at"):
            raise ValueError("Search returned an unmerged pull request")
        url = item["html_url"]
        match = re.fullmatch(r"https://github.com/([^/]+)/([^/]+)/pull/([0-9]+)", url)
        if not match:
            raise ValueError("Invalid pull request URL")
        owner, repo, number = match.groups()
        if owner.casefold() == USERNAME.casefold():
            raise ValueError("Search returned a pull request in a personal repository")
        project = (owner, repo)
        title = escape_text(display_title(item["title"]))
        projects.setdefault(project, []).append(
            f"- [{title}]({url}) <sub>#{number}</sub>"
        )
    lines = []
    for (owner, repo), contributions in projects.items():
        lines.extend([
            f"### [{escape_text(repo)}](https://github.com/{owner}/{repo}) "
            f"<sub>· {escape_text(owner)}</sub>",
            "",
            *contributions,
            "",
        ])
    if not items:
        lines = ["No merged public pull requests yet."]
    all_prs = "https://github.com/pulls?" + urlencode({"q": QUERY})
    return "\n".join(lines).rstrip() + f"\n\n[Explore all merged contributions →]({all_prs})"


def replace_section(readme, content):
    if readme.count(START) != 1 or readme.count(END) != 1:
        raise ValueError("README must contain exactly one pair of contribution markers")
    before, remaining = readme.split(START)
    _, after = remaining.split(END)
    return before + START + "\n\n" + content + "\n\n" + END + after


def main():
    original = README.read_text(encoding="utf-8")
    updated = replace_section(original, render_contributions(fetch_contributions()))
    if updated != original:
        README.write_text(updated, encoding="utf-8")
        print("Updated README contributions")
    else:
        print("Contributions are unchanged")


if __name__ == "__main__":
    main()
