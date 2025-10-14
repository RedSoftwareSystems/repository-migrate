import os
import sys
import pathlib
from typing import Annotated, Optional

import typer
from loguru import logger
import re

from repo_utils import ghutils
from repo_utils import bbutils
from repo_utils import utils

app = typer.Typer()

DEFAULT_WORKING_DIR: str = "./git_migration_working_dir"

logger_level = os.getenv("LOGURU_LEVEL", "INFO")
logger.remove()
logger.add(sys.stderr, level=logger_level)


def check_working_dir(working_directory: str) -> str:
    full_working_directory = os.path.expanduser(working_directory)
    os.path.exists(full_working_directory) or os.mkdir(full_working_directory, 0o775)

    return full_working_directory


def process_repo(slug: str, desc: str, private: bool):
    gh_repo = ghutils.gh_get_repo(slug)
    #
    if gh_repo is None:
        ghutils.gh_repo_create(slug, desc, private)

    # bb_clone_repo(slug)
    # gh_repo_push(slug)
    return True


@app.command("list-github-repositories")
def list_github_repositories(
    github_organization: str,
    github_token: Annotated[str, typer.Argument(envvar="GITHUB_TOKEN")],
    short_format: Annotated[
        bool,
        typer.Option(
            help="Print only the slug of the repo (useful for redirection to file)"
        ),
    ] = False,
):
    gh_repositories = ghutils.gh_get_repositories(github_organization, github_token)

    for count, gh_repo in enumerate(gh_repositories):
        if short_format:
            print(gh_repo.name)
        else:
            print(
                f"{count} Name: {gh_repo.name}\tFull Name: {gh_repo.full_name}\tDescription: {gh_repo.description}"
            )


@app.command("compare-bitbucket-github-organization")
def compare_bitbucket_github_organization(
    bitbucket_organization: Annotated[
        str, typer.Argument(envvar="BITBUCKET_ORGANIZATION")
    ],
    bitbucket_username: Annotated[str, typer.Argument(envvar="BITBUCKET_USERNAME")],
    bitbucket_password: Annotated[str, typer.Argument(envvar="BITBUCKET_PASSWORD")],
    github_organization: Annotated[str, typer.Argument(envvar="GITHUB_ORGANIZATION")],
    github_token: Annotated[str, typer.Argument(envvar="GITHUB_TOKEN")],
    only_bitbucket: Annotated[
        bool, typer.Option(help="Print repos only present in BitBucket")
    ] = False,
    only_github: Annotated[
        bool, typer.Option(help="Print repos only present in GitHub")
    ] = False,
):
    match_repos = utils.get_matching_repos(
        bitbucket_organization,
        bitbucket_password,
        bitbucket_username,
        github_organization,
        github_token,
    )
    if only_bitbucket:
        print("Bitbucket Repositories not present in GitHub")
        for element in match_repos:
            if (match_repos[element].get("gh_url") is None) and (
                match_repos[element].get("bb_url") is not None
            ):
                print(element)
    if only_github:
        print("GitHub Repositories not present in BitBucket")
        for element in match_repos:
            if (match_repos[element].get("bb_url") is None) and (
                match_repos[element].get("gh_url") is not None
            ):
                print(element)
    if (not only_bitbucket) & (not only_github):
        # oredered_match_repos = sorted(match_repos, key=lambda repo: repo.get('gh_url'))
        ordered_match_repos = sorted(match_repos)
        for element in ordered_match_repos:
            print(
                f"{element}\t\t{match_repos[element].get('gh_url')}\t\t{match_repos[element].get('bb_url')}"
            )


def migrate_repositories(
    bitbucket_organization: str,
    bitbucket_username: str,
    bitbucket_password: str,
    github_organization: str,
    github_token: str,
    working_dir: str,
    from_gh_to_bb: bool,
    already_pulled: bool,
) -> None:
    p = pathlib.Path(working_dir)
    logger.debug(f"Working directory: {working_dir}")
    if already_pulled:
        logger.info(
            f"Working on already cloned repositories in directory: {working_dir}"
        )
        for child in p.iterdir():
            if child.is_dir():
                logger.info(f"Examining Repo: {child.name}")
                gh_repo = ghutils.gh_get_repo(child.stem, github_organization, github_token)
                if gh_repo is not None:
                    logger.info(f"Repo: {gh_repo.name} Already Exists, skipping")

                else:
                    logger.info(
                        f"Creating new Repo: {child.stem} Already Exists, skipping"
                    )
                    ghutils.gh_repo_create(
                        child.stem, "", True, github_organization, github_token
                    )
                    logger.info(f"Pushing Repo: {child.stem}")
                    utils.git_push_repo(
                        child.stem, github_organization, "github.com", working_dir
                    )
    else:
        logger.info("Starting from a clean state")


@app.command("set-bb-project-as-gh-topic")
def set_bb_project_as_gh_topic(
    bitbucket_organization: Annotated[
        str,
        typer.Argument(envvar="BITBUCKET_ORGANIZATION", help="Bitbucket Organization"),
    ],
    bitbucket_username: Annotated[
        str, typer.Argument(envvar="BITBUCKET_USERNAME", help="Bitbucket UserName")
    ],
    bitbucket_password: Annotated[
        str, typer.Argument(envvar="BITBUCKET_PASSWORD", help="Bitbucket Password")
    ],
    github_organization: Annotated[
        str, typer.Argument(envvar="GITHUB_ORGANIZATION", help="GitHub Organization")
    ],
    github_token: Annotated[
        str, typer.Argument(envvar="GITHUB_TOKEN", help="GitHub Token")
    ],
) -> None:
    logger.debug("Retrieving list of BitBucket Projects")
    projects = bbutils.bb_get_projects(
        bitbucket_organization, bitbucket_username, bitbucket_password
    )

    for project in projects.each():
        project_name = project.name
        project_topics = re.split(r"[\s-]+", project_name)
        project_key = project.key
        logger.debug(f"{project_name} {project_topics} {project_key} ")
        for repo in project.repositories.each():
            logger.debug(f"{project_name}\t{repo.name} \t{repo.slug}")
            gh_repo = ghutils.gh_get_repo(repo.slug, github_organization, github_token)
            gh_repo_topics = gh_repo.get_topics()
            new_topics = []
            for topic in project_topics:
                new_topics.append(topic.lower().replace("_", "-"))
            for topic in gh_repo_topics:
                new_topics.append(topic.lower().replace("_", "-"))

            new_topics.append(project_key.lower().replace("_", "-"))
            new_topics = list(dict.fromkeys(new_topics))
            logger.info(f"Setting Topics: {new_topics} for repo: {repo.slug}")
            gh_repo.replace_topics(new_topics)

    return None


@app.command("create-team-from-bb-project")
def create_team_from_bb_project(
    bitbucket_organization: Annotated[
        str,
        typer.Argument(envvar="BITBUCKET_ORGANIZATION", help="Bitbucket Organization"),
    ],
    bitbucket_username: Annotated[
        str, typer.Argument(envvar="BITBUCKET_USERNAME", help="Bitbucket UserName")
    ],
    bitbucket_password: Annotated[
        str, typer.Argument(envvar="BITBUCKET_PASSWORD", help="Bitbucket Password")
    ],
    github_organization: Annotated[
        str, typer.Argument(envvar="GITHUB_ORGANIZATION", help="GitHub Organization")
    ],
    github_token: Annotated[
        str, typer.Argument(envvar="GITHUB_TOKEN", help="GitHub Token")
    ],
) -> None:
    logger.debug("Retrieving list of BitBucket Projects")
    projects = bbutils.bb_get_projects(
        bitbucket_organization, bitbucket_username, bitbucket_password
    )
    for project in projects.each():
        team = bbutils.create_team_from_bb_prj(
            bitbucket_organization, bitbucket_username, bitbucket_password, project
        )
        if team is not None:
            logger.info(f"Creating Team: {team.name}")


@app.command("migrate-repositories-bb-to-gh")
def migrate_repositories_bb_to_gh(
    bitbucket_organization: Annotated[
        str,
        typer.Argument(envvar="BITBUCKET_ORGANIZATION", help="Bitbucket Organization"),
    ],
    bitbucket_username: Annotated[
        str, typer.Argument(envvar="BITBUCKET_USERNAME", help="Bitbucket UserName")
    ],
    bitbucket_password: Annotated[
        str, typer.Argument(envvar="BITBUCKET_PASSWORD", help="Bitbucket Password")
    ],
    github_organization: Annotated[
        str, typer.Argument(envvar="GITHUB_ORGANIZATION", help="GitHub Organization")
    ],
    github_token: Annotated[
        str, typer.Argument(envvar="GITHUB_TOKEN", help="GitHub Token")
    ],
    working_dir: Annotated[
        Optional[str],
        typer.Argument(
            envvar="MIGRATION_WORKING_DIR",
            help="Working Directory for Pull / Push operations",
        ),
    ] = "git_migration_working_dir",
    already_pulled: Annotated[
        bool,
        typer.Option(
            help="Cycles in Working Directory for already pulled repositories"
        ),
    ] = False,
):
    """
    Migrates BitBucket repositories from GitHub to BitBucket.

    """
    migrate_repositories(
        bitbucket_organization,
        bitbucket_username,
        bitbucket_password,
        github_organization,
        github_token,
        check_working_dir(working_dir),
        False,
        already_pulled,
    )


@app.command("migrate-repositories-gh-to-bb")
def migrate_repositories_gh_to_bb(
    bitbucket_organization: Annotated[
        str, typer.Argument(envvar="BITBUCKET_ORGANIZATION")
    ],
    bitbucket_username: Annotated[str, typer.Argument(envvar="BITBUCKET_USERNAME")],
    bitbucket_password: Annotated[str, typer.Argument(envvar="BITBUCKET_PASSWORD")],
    github_organization: Annotated[str, typer.Argument(envvar="GITHUB_ORGANIZATION")],
    github_token: Annotated[str, typer.Argument(envvar="GITHUB_TOKEN")],
    working_dir: Annotated[
        Optional[str], typer.Argument(envvar="MIGRATION_WORKING_DIR")
    ] = "git_migration_working_dir",
):
    migrate_repositories(
        bitbucket_organization,
        bitbucket_username,
        bitbucket_password,
        github_organization,
        github_token,
        working_dir,
        True,
    )


@app.command("migrate-list-of-repositories")
def migrate_list_of_repositories():
    pass


@app.command("list-bitbucket-repositories")
def list_bitbucket_repositories(
    bitbucket_organization: Annotated[str, typer.Argument(envvar="BITBUCKET_ORGANIZATION")],
    bitbucket_username: Annotated[str, typer.Argument(envvar="BITBUCKET_USERNAME")],
    bitbucket_password: Annotated[str, typer.Argument(envvar="BITBUCKET_PASSWORD")],
    short_format: Annotated[
        bool,
        typer.Option(
            help="Print only the slug of the repo (useful for redirection to file)"
        ),
    ] = False,
):
    repositories = bbutils.bb_get_repositories(
        bitbucket_organization, bitbucket_username, bitbucket_password
    )

    for repo in repositories.each():
        if short_format:
            print(f"{repo.slug}")
        else:
            print(
                f"Name: {repo.name:<50}Slug: {repo.slug:<50} Description:{repo.description[:60]:<60} is private:{repo.is_private}"
            )


def main() -> None:
    WORKING_DIR = os.path.expanduser(DEFAULT_WORKING_DIR)
    os.path.exists(WORKING_DIR) or os.mkdir(WORKING_DIR, 0o775)


if __name__ == "__main__":
    # main()
    app()
