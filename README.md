# repository-migrate
Migrate your repositories, BitBucket to GitHub (and vice versa)

## How to run
Best option (until I properly package this for pypi) is to install [uv](https://docs.astral.sh/uv/getting-started/installation/) 

```
uv run repository-migrate.py --help 
```

## Available Commands
* list-bitbucket-repositories
* list-github-repositories - list github repositories of your organization
* compare-bitbucket-github - compare (via slug) repositories presence between the two services


## Inspired from: 
* Article https://esolitos.com/items/2019/07/automatically-move-my-git-repositories-bitbucket-github
* GIST https://gist.github.com/esolitos/da1083f57ac7e3f38cc8225cd00b11e6



