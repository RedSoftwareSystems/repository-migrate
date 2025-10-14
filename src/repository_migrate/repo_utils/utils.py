import os
import subprocess

from loguru import logger

from repo_utils import ghutils
from repo_utils import bbutils


def git_push_repo(slug: str, organization: str, service: str, working_dir: str) -> bool:
    logger.info(f"Pushing Repo {slug} Organization: {organization}")
    repo_dir = os.path.join(working_dir, "%s.git" % slug)
    logger.debug(f"repo_dir: {repo_dir}")
    args = [
        "git",
        "push",
        "--mirror",
        "git@%s:%s/%s.git" % (service, organization, slug),
    ]
    process = subprocess.Popen(
        args, cwd=repo_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )

    stdout, stderr = process.communicate()
    if stderr is not None:
        print(stderr.decode())
        return False

    print("Push: %s" % stdout.decode())
    return True


def git_clone_repo(
    slug: str, organization: str, service: str, working_dir: str
) -> bool:
    dest = os.path.join(working_dir, "%s.git" % slug)
    if os.path.isdir(dest):
        # Assume we have already cloned the repo.
        return True

    args = [
        "git",
        "clone",
        "--bare",
        "git@%s:%s/%s.git" % (service, organization, slug),
    ]
    process = subprocess.Popen(
        args, cwd=working_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )

    stdout, stderr = process.communicate()
    if stderr is not None:
        print(stderr.decode())
        return False

    print("Clone: %s" % stdout.decode())
    return True


def get_matching_repos(
    bitbucket_organization,
    bitbucket_password,
    bitbucket_username,
    github_organization,
    github_token,
) -> dict[str, dict]:
    match_repos = dict()
    repositories = bbutils.bb_get_repositories(
        bitbucket_organization, bitbucket_username, bitbucket_password
    )
    for repo in repositories.each():
        match_repos[repo.slug] = {"bb_url": repo.url}
    for gh_repo in ghutils.gh_get_repositories(github_organization, github_token):
        if gh_repo.name in match_repos.keys():
            match_repos[gh_repo.name]["gh_url"] = gh_repo.url
        else:
            match_repos[gh_repo.name] = {"gh_url": gh_repo.url}
    return match_repos
