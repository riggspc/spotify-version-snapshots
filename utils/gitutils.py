import git
from datetime import datetime

from git import NoSuchPathError, Commit

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
    # A temp commit is needed to get stats etc - the library doesn't support it
    # otherwise
    commit = repo.index.commit("temp")
    commit_message = get_commit_message_for_amending(commit)
    repo.git.commit("--amend", "-m", commit_message)


def get_commit_message_for_amending(commit: Commit) -> str:
    commit_title = f'Spotify Snapshot - {datetime.now().strftime("%m/%d/%Y, %H:%M:%S")}'
    stats = commit.stats
    playlist_additions = 0
    playlist_removals = 0
    for changed_file in stats.files:
        if changed_file in {"playlists.tsv", "saved_albums.tsv", "saved_tracks.tsv"}:
            continue
        playlist_additions += stats.files[changed_file]["insertions"]
        playlist_removals += stats.files[changed_file]["deletions"]
    commit_details = []
    if "saved_tracks.tsv" in stats.files:
        commit_details.extend(
            [
                f"Added Songs: {stats.files['saved_tracks.tsv']['insertions']}",
                f"Removed Songs: {stats.files['saved_tracks.tsv']['deletions']}",
            ]
        )
    if "saved_albums.tsv" in stats.files:
        commit_details.extend(
            [
                f"Added Albums: {stats.files['saved_albums.tsv']['insertions']}",
                f"Removed Albums: {stats.files['saved_albums.tsv']['deletions']}",
            ]
        )
    if "playlists.tsv" in stats.files:
        commit_details.extend(
            [
                f"Added Playlists: {stats.files['playlists.tsv']['insertions']}",
                f"Removed Playlists: {stats.files['playlists.tsv']['deletions']}",
            ]
        )
    commit_details.extend(
        [
            f"Total Additions Across Playlists: {playlist_additions}",
            f"Total Removals Across Playlists: {playlist_removals}",
        ]
    )

    commit_message_body = "\n".join(commit_details)

    return "\n\n".join([commit_title, commit_message_body])
