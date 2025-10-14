from github import BadCredentialsException, UnknownObjectException, Auth, Github
from loguru import logger


def gh_repo_create(
    name: str, description: str, is_private: bool, gh_organization: str, gh_token: str
):
    logger.info(f"Creating Repo {name} Organization: {gh_organization}")
    gh = github(gh_token)
    organization = gh.get_organization(gh_organization)
    result = organization.create_repo(
        name,
        allow_rebase_merge=True,
        auto_init=False,
        description=description,
        private=is_private,
    )
    return result


def gh_get_repo(repo_slug: str, gh_organization: str, gh_token: str):
    try:
        gh = github(gh_token)
        organization = gh.get_organization(gh_organization)
        repo = organization.get_repo(repo_slug)
        return repo
    except BadCredentialsException as badex:
        logger.error("Bad GitHub Credentials", badex)
        return None
    except UnknownObjectException as ex:
        logger.error("Unknown GitHub Organization or Repository", ex)
        print(ex)
        return None


def github(auth_token: str):
    auth = Auth.Token(auth_token)
    git_hub = Github(auth=auth)
    return git_hub


def gh_get_repositories(organization_name: str, gh_token: str):
    organization = github(gh_token).get_organization(organization_name)
    return organization.get_repos()
