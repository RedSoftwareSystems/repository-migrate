from atlassian.bitbucket import Cloud


def bitbucket_cloud(username: str, password: str):
    return Cloud(username=username, password=password, cloud=True)


def bb_get_repositories(workspace_name: str, bb_username: str, bb_password: str):
    workspace = bitbucket_cloud(bb_username, bb_password).workspaces.get(workspace_name)
    return workspace.repositories


def bb_get_projects(
    bitbucket_organization: str, bitbucket_username: str, bitbucket_password: str
):
    workspace = bitbucket_cloud(bitbucket_username, bitbucket_password).workspaces.get(
        bitbucket_organization
    )
    return workspace.projects


def create_team_from_bb_prj(
    bitbucket_organization, bitbucket_username, bitbucket_password, project
):
    pass
