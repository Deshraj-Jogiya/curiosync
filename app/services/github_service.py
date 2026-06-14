"""Service to fetch public GitHub repositories for Monday project spotlight posts."""

import httpx
from app.utils.logging import logger


async def fetch_github_projects(username: str) -> list[dict]:
    """Fetch public repositories for a given GitHub username.

    Returns a list of dicts with keys: name, html_url, description, language, stargazers_count, topics.
    """
    if not username or username == "your-github-username":
        logger.warning(
            "No valid GitHub username configured, skipping repository fetch."
        )
        return []

    url = f"https://api.github.com/users/{username}/repos"
    headers = {"Accept": "application/vnd.github.v3+json"}

    logger.info("Fetching GitHub projects", extra={"username": username})

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=10.0)
            if response.status_code != 200:
                logger.error(
                    "Failed to fetch GitHub repositories",
                    extra={
                        "username": username,
                        "status_code": response.status_code,
                        "body": response.text[:200],
                    },
                )
                return []

            repos = response.json()
            if not isinstance(repos, list):
                logger.error(
                    "GitHub API response is not a list",
                    extra={"username": username},
                )
                return []

            results = []
            for repo in repos:
                # Filter out forks
                if repo.get("fork", False):
                    continue
                results.append(
                    {
                        "name": repo.get("name"),
                        "html_url": repo.get("html_url"),
                        "description": repo.get("description"),
                        "language": repo.get("language"),
                        "stargazers_count": repo.get("stargazers_count", 0),
                        "topics": repo.get("topics", []),
                    }
                )

            # Sort by stargazers desc, then name
            results.sort(
                key=lambda r: (
                    -r["stargazers_count"],
                    r["name"].lower() if r["name"] else "",
                )
            )
            logger.info(
                "GitHub projects fetched successfully",
                extra={"username": username, "count": len(results)},
            )
            return results

    except Exception as exc:
        logger.exception(
            "Exception while fetching GitHub repositories",
            extra={"username": username},
        )
        return []
