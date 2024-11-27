import argparse
import os
import sys
import pathlib
import subprocess
from typing import Annotated, Optional

import typer
from atlassian.bitbucket import Cloud
from github import Auth
from github import Github
from github import BadCredentialsException
from github import UnknownObjectException
from loguru import logger

app = typer.Typer()

DEFAULT_WORKING_DIR : str = './git_migration_working_dir'

logger_level = os.getenv("LOGURU_LEVEL","INFO")
logger.remove()
logger.add(sys.stderr, level=logger_level)


def check_working_dir(working_directory : str) -> str:
    full_working_directory = os.path.expanduser(working_directory)
    os.path.exists(full_working_directory) or os.mkdir(full_working_directory, 0o775)

    return full_working_directory

def bitbucket_cloud(username : str,password:str):
    return Cloud( username=username,
                  password=password,
                  cloud=True)

def github(auth_token:str):
    auth = Auth.Token(auth_token)
    git_hub = Github(auth=auth)
    return git_hub


def bb_get_repositories(workspace_name: str, bb_username:str, bb_password:str) :
    workspace = bitbucket_cloud(bb_username,bb_password).workspaces.get(workspace_name)
    return workspace.repositories


def gh_get_repositories(organization_name: str, gh_token: str):
    organization = github(gh_token).get_organization(organization_name)
    return organization.get_repos()


def git_clone_repo(slug: str, organization: str, service: str, working_dir: str) -> None:
    dest = os.path.join(working_dir, '%s.git' % slug)
    if os.path.isdir(dest):
        # Assume we have already cloned the repo.
        return True


    args = [
        'git',
        'clone',
        '--bare',
        'git@%s:%s/%s.git' % (service,organization, slug)
    ]
    process = subprocess.Popen(args, cwd=working_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    stdout, stderr = process.communicate()
    if stderr is not None:
        print(stderr.decode())
        return False

    print('Clone: %s' % stdout.decode())
    return True


def gh_get_repo(repo_slug: str, gh_organization: str, gh_token: str):
    try:
        gh = github(gh_token)
        organization = gh.get_organization(gh_organization)
        repo = organization.get_repo(repo_slug)
        return repo
    except BadCredentialsException as badex:
        logger.error('Bad GitHub Credentials',badex)
        return None
    except UnknownObjectException as ex:
        logger.error('Unknown GitHub Organization or Repository',ex)
        print(ex)
        return None

def gh_repo_create(name: str, description: str, is_private: bool,gh_organization: str, gh_token:str):
    logger.info(f'Creating Repo {name} Organization: {gh_organization}')
    gh = github(gh_token)
    organization = gh.get_organization(gh_organization)
    result = organization.create_repo(
        name,
        allow_rebase_merge=True,
        auto_init=False,
        description=description,
        private=is_private
       )
    return result


def git_push_repo(slug: str, organization: str, service:str, working_dir: str) -> bool:
    logger.info(f'Pushing Repo {slug} Organization: {organization}')
    repo_dir = os.path.join(working_dir, '%s.git' % slug)
    logger.debug(f"repo_dir: {repo_dir}")
    args = [
        'git',
        'push',
        '--mirror',
        'git@%s:%s/%s.git' % (service, organization, slug)
    ]
    process = subprocess.Popen(args, cwd=repo_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    stdout, stderr = process.communicate()
    if stderr is not None:
        print(stderr.decode())
        return False

    print('Push: %s' % stdout.decode())
    return True


def process_repo(slug: str, desc: str, private: bool):
    gh_repo = gh_get_repo(slug)
    #
    if gh_repo is None:
          gh_repo_create(slug, desc, private)

    # bb_clone_repo(slug)
    # gh_repo_push(slug)
    return True



@app.command("list-github-repositories")
def list_github_repositories(github_organization: str,
                                github_token: Annotated[str,typer.Argument(envvar="GITHUB_TOKEN")],
                                short_format: Annotated[bool,
                                typer.Option(help="Print only the slug of the repo (useful for redirection to file)")]= False,):

    gh_repositories = gh_get_repositories(github_organization, github_token)

    for gh_repo in gh_repositories:
        if (short_format):
            print(gh_repo.name)
        else:
            print(f"Name: {gh_repo.name}\tFull Name: {gh_repo.full_name}\tDescription: {gh_repo.description}")

@app.command("list-bitbucket-repositories")
def list_bitbucket_repositories(organization_name: str,
                                bitbucket_username: Annotated[str,typer.Argument(envvar="BITBUCKET_USERNAME")],
                                bitbucket_password:Annotated[str,typer.Argument(envvar="BITBUCKET_PASSWORD")],
                                short_format: Annotated[bool,
                                typer.Option(help="Print only the slug of the repo (useful for redirection to file)")]= False,):
    repositories = bb_get_repositories(organization_name,bitbucket_username,bitbucket_password)

    for repo in repositories.each():
        if short_format:
            print(f"{repo.slug}")
        else:
            print(f'Slug: {repo.slug:<50} Description:{repo.description[:60]:<60} is private:{repo.is_private}')


@app.command("compare-bitbucket-github-organization")
def compare_bitbucket_github_organization(bitbucket_organization_name: Annotated[str,typer.Argument(envvar="BITBUCKET_ORGANIZATION")],
                                bitbucket_username: Annotated[str,typer.Argument(envvar="BITBUCKET_USERNAME")],
                                bitbucket_password: Annotated[str,typer.Argument(envvar="BITBUCKET_PASSWORD")],
                                github_organization: Annotated[str,typer.Argument(envvar="GITHUB_ORGANIZATION")],
                                github_token: Annotated[str,typer.Argument(envvar="GITHUB_TOKEN")],
                                only_bitbucket: Annotated[bool,
                                typer.Option(help="Print repos only present in BitBucket")]= False,
                                only_github: Annotated[bool,
                                typer.Option(help="Print repos only present in GitHub")]= False
):

    match_repos = get_matching_repos(bitbucket_organization_name,
                                     bitbucket_password, bitbucket_username,
                                     github_organization, github_token)
    if (only_bitbucket):
        print("Bitbucket Repositories not present in GitHub")
        for element in match_repos:
            if (match_repos[element].get('gh_url') is None) and (match_repos[element].get('bb_url') is not None):
                print(element)
    if (only_github):
        print("GitHub Repositories not present in BitBucket")
        for element in match_repos:
            if (match_repos[element].get('bb_url') is None) and (match_repos[element].get('gh_url') is not None):
                print(element)
    if (not only_bitbucket) & (not only_github):
        for element in match_repos:
            print(f"{element}\t\t{match_repos[element].get('gh_url')}\t\t{match_repos[element].get('bb_url')}")



def get_matching_repos(bitbucket_organization_name, bitbucket_password,
    bitbucket_username, github_organization, github_token):
    match_repos = dict()
    repositories = bb_get_repositories(bitbucket_organization_name,
                                       bitbucket_username,
                                       bitbucket_password)
    for repo in repositories.each():
        match_repos[repo.slug] = {"bb_url": repo.url}
    for gh_repo in gh_get_repositories(github_organization, github_token):
        if (gh_repo.name in match_repos.keys()):
            match_repos[gh_repo.name]['gh_url'] = gh_repo.url
        else:
            match_repos[gh_repo.name] = {"gh_url": gh_repo.url}
    return match_repos


def migrate_repositories(bitbucket_organization_name: str,
                                bitbucket_username: str,
                                bitbucket_password: str,
                                github_organization: str,
                                github_token: str,
                                working_dir: str,
                                from_gh_to_bb: bool,
                                already_pulled: bool) -> None:

    p =  pathlib.Path(working_dir)
    logger.debug(f"Working directory: {working_dir}")
    if (already_pulled):
        logger.info(f"Working on already cloned repositories in directory: {working_dir}")
        for child in p.iterdir():
            if child.is_dir():
                logger.info(f"Examining Repo: {child.name}")
                gh_repo = gh_get_repo(child.stem, github_organization,github_token)
                if (gh_repo is not None):
                    logger.info(f"Repo: {gh_repo.name} Already Exists, skipping")

                else:
                    logger.info(
                        f"Creating new Repo: {child.stem} Already Exists, skipping")
                    gh_repo_create(child.stem,"",True,github_organization,github_token)
                    logger.info(
                        f"Pushing Repo: {child.stem}")
                    git_push_repo(child.stem,github_organization,"github.com",working_dir)
    else:
        logger.info(f"Starting from a clean state")




@app.command("set-bb-project-as-gh-topic")
def set_bb_project_as_gh_topic(bitbucket_organization_name: Annotated[str,typer.Argument(envvar="BITBUCKET_ORGANIZATION",help="Bitbucket Organization")],
                                bitbucket_username: Annotated[str,typer.Argument(envvar="BITBUCKET_USERNAME",help="Bitbucket UserName")],
                                bitbucket_password: Annotated[str,typer.Argument(envvar="BITBUCKET_PASSWORD", help="Bitbucket Password")],
                                github_organization: Annotated[str,typer.Argument(envvar="GITHUB_ORGANIZATION",help="GitHub Organization")],
                                github_token: Annotated[str,typer.Argument(envvar="GITHUB_TOKEN",help="GitHub Token")] ) -> None:

    return None




@app.command("migrate-repositories-bb-to-gh")
def migrate_repositories_bb_to_gh(bitbucket_organization_name: Annotated[str,typer.Argument(envvar="BITBUCKET_ORGANIZATION",help="Bitbucket Organization")],
                                bitbucket_username: Annotated[str,typer.Argument(envvar="BITBUCKET_USERNAME",help="Bitbucket UserName")],
                                bitbucket_password: Annotated[str,typer.Argument(envvar="BITBUCKET_PASSWORD", help="Bitbucket Password")],
                                github_organization: Annotated[str,typer.Argument(envvar="GITHUB_ORGANIZATION",help="GitHub Organization")],
                                github_token: Annotated[str,typer.Argument(envvar="GITHUB_TOKEN",help="GitHub Token")],
                                working_dir: Annotated[Optional[str],typer.Argument(envvar="MIGRATION_WORKING_DIR",help="Working Directory for Pull / Push operations")] = "git_migration_working_dir",
                                already_pulled: Annotated[bool,typer.Option(help="Cycles in Working Directory for already pulled repositories")] = False):
    """
    Migrates BitBucket repositories from GitHub to BitBucket.

    """
    migrate_repositories(bitbucket_organization_name,bitbucket_username,bitbucket_password,github_organization,github_token,check_working_dir(working_dir),False,already_pulled)

@app.command("migrate-repositories-gh-to-bb")
def migrate_repositories_gh_to_bb(bitbucket_organization_name: Annotated[str,typer.Argument(envvar="BITBUCKET_ORGANIZATION")],
                                bitbucket_username: Annotated[str,typer.Argument(envvar="BITBUCKET_USERNAME")],
                                bitbucket_password: Annotated[str,typer.Argument(envvar="BITBUCKET_PASSWORD")],
                                github_organization: Annotated[str,typer.Argument(envvar="GITHUB_ORGANIZATION")],
                                github_token: Annotated[str,typer.Argument(envvar="GITHUB_TOKEN")],
                                working_dir: Annotated[Optional[str],typer.Argument(envvar="MIGRATION_WORKING_DIR")] = "git_migration_working_dir"):

    migrate_repositories(bitbucket_organization_name,bitbucket_username,bitbucket_password,github_organization,github_token,working_dir,True)


@app.command("migrate-list-of-repositories")
def migrate_list_of_repositories():
    pass




def main() -> None:
    WORKING_DIR = os.path.expanduser(DEFAULT_WORKING_DIR)
    os.path.exists(WORKING_DIR) or os.mkdir(WORKING_DIR, 0o775)


if __name__ == '__main__':
    #main()
    app()





