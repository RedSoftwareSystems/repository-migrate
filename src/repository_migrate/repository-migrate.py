import os
from pprint import pprint
import subprocess
from typing import Annotated

import typer
from atlassian.bitbucket import Cloud
from github import Auth
from github import Github
from github.Repository import Repository as github_Repository


app = typer.Typer()

DEFAULT_WORKING_DIR : str = '../../migration_working_dir'


def bitbucket_cloud(username : str,password:str):
    return Cloud( username=username,
                  password=password,
                  cloud=True)

def github(auth_token:str):
    auth = Auth.Token(auth_token)
    g = Github(auth=auth)
    return g


def bb_get_repositories(workspace_name: str, bb_username:str, bb_password:str) :
    workspace = bitbucket_cloud(bb_username,bb_password).workspaces.get(workspace_name)

    return workspace.repositories


def gh_get_repositories(organization_name: str, gh_token: str):
    organization = github(gh_token).get_organization("redsoftwaresystems")
    return organization.get_repos()


def bb_clone_repo(slug: str, bb_organization: str):
    dest = os.path.join(WORKING_DIR, '%s.git' % slug)
    if os.path.isdir(dest):
        # Assume we have already cloned the repo.
        return True

    args = [
        'git',
        'clone',
        '--bare',
        'git@bitbucket.org:%s/%s.git' % (bb_organization, slug)
    ]
    process = subprocess.Popen(args, cwd=WORKING_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    stdout, stderr = process.communicate()
    if stderr is not None:
        print(stderr.decode())
        return False

    print('Clone: %s' % stdout.decode())
    return True


def gh_get_repo(repo_slug: str, gh_token: str):
    try:
        return github(gh_token).get_repo(repo_slug)
    except:
        return None

def gh_repo_create(name: str, description: str, is_private: bool,gh_organization: str):
    gh = github()
    organization = gh.get_organization(gh_organization)
    organization.create_repo(
        name,
        allow_rebase_merge=True,
        auto_init=False,
        description=description,
        private=is_private
       )


def gh_repo_push(slug: str, gh_organization):
    repo_dir = os.path.join(WORKING_DIR, '%s.git' % slug)
    args = [
        'git',
        'push',
        '--mirror',
        'git@github.com:%s/%s.git' % (gh_organization, slug)
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

    bb_clone_repo(slug)
    gh_repo_push(slug)
    return True

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
def compare_bitbucket_github_organization(bitbucket_organization_name: str,
                                bitbucket_username: Annotated[str,typer.Argument(envvar="BITBUCKET_USERNAME")],
                                bitbucket_password: Annotated[str,typer.Argument(envvar="BITBUCKET_PASSWORD")],
                                github_organization: str,
                                github_token: Annotated[str,typer.Argument(envvar="GITHUB_TOKEN")],
                                only_bitbucket: Annotated[bool,
                                typer.Option(help="Print repos only present in BitBucket (useful for redirection to file)")]= False,
                                only_github: Annotated[bool,
                                typer.Option(help="Print repos only present in GitHub (useful for redirection to file)")]= False
):
    match_repos = dict()
    repositories = bb_get_repositories(bitbucket_organization_name, bitbucket_username,
                                       bitbucket_password)
    for repo in repositories.each():
          match_repos[repo.name] = {"bb_url": repo.url}

    for gh_repo in gh_get_repositories(github_organization, github_token):
        if (gh_repo.name in match_repos.keys()):
            match_repos[gh_repo.name]['gh_url'] = gh_repo.url
        else:
            match_repos[gh_repo.name] = {"gh_url": gh_repo.url}
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

@app.command("migrate-repositories")
def migrate_repositories():
    pass


@app.command("migrate-list-of-repositories")
def migrate_list_of_repositories():
    pass

if __name__ == '__main__':
    WORKING_DIR = os.path.expanduser(DEFAULT_WORKING_DIR)
    os.path.exists(WORKING_DIR) or os.mkdir(WORKING_DIR, 0o775)
    app()

    # Create CWD if needed


