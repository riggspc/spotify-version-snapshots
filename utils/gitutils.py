import git

from git import NoSuchPathError

SNAPSHOTS_REPO_NAME = "spotify-snapshots-repo"

def setup_git_repo_if_needed() -> None:
    try:
        my_repo = git.Repo(SNAPSHOTS_REPO_NAME)
        print("Found existing repo")
    except NoSuchPathError as e:
        print("No repo, making a new one")
        new_repo = git.Repo.init(SNAPSHOTS_REPO_NAME)


# Assumes repo already exists etc
def commit_files() -> None:
    repo = git.Repo(SNAPSHOTS_REPO_NAME)
    repo.index.add(items="*")
    # TODO: make this message something meaningful
    repo.index.commit('test commit')