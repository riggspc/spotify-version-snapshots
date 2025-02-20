import git
from datetime import datetime
from rich import print as rprint

from git import NoSuchPathError, Commit
from spotify_version_snapshots import constants

FILENAMES = constants.FILENAMES


def get_repo_name(is_test_mode: bool) -> str:
    if is_test_mode:
        return "/tmp/SPOTIFY-VERSION-SNAPSHOTS-TEST-REPO"
    else:
        return "spotify-snapshots-repo"


def setup_git_repo_if_needed(is_test_mode) -> None:
    repo_name = get_repo_name(is_test_mode)
    try:
        git.Repo(repo_name)
        rprint(
            f"[yellow]Found existing repo at[/yellow] [green][bold]{repo_name}[/bold][/green]"
        )
    except NoSuchPathError as e:
        rprint(
            f"[yellow]No repo found, making a new one at[/yellow] [green][bold]{repo_name}[/bold][/green]"
        )
        git.Repo.init(repo_name)


# Assumes repo already exists etc
def commit_files(is_test_mode) -> None:
    repo = git.Repo(get_repo_name(is_test_mode))

    # Check if there are any changes to commit
    if not repo.is_dirty(untracked_files=True):
        rprint("[yellow]No changes to commit[/yellow]")
        return

    repo.index.add(items="*")
    # A temp commit is needed to get stats etc - the library doesn't support it
    # otherwise
    commit = repo.index.commit("temp")
    commit_message = get_commit_message_for_amending(commit)
    rprint(
        f"[green]Commit info:[/green]\n\n[yellow][bold]{commit_message}[/bold][/yellow]"
    )
    repo.git.commit("--amend", "-m", commit_message)
    rprint("[green]Changes committed. All done![/green]")


def get_commit_message_for_amending(commit: Commit) -> str:
    """
    Generate a contextually appropriate commit message (depending on whether this is the first commit or not)
    If it is the first commit, the git commit is a status report on how many playlists were backed up, how many tracks per playlist, and how many liked songs were backed up
    For all commits after, the git commit is a status report on how many playlists were added, removed, and how many tracks were added, removed
    """
    is_first_commit = len(commit.parents) == 0
    current_time = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
    if is_first_commit:
        commit_title = f"Initial Spotify Snapshot - {current_time}"
    else:
        commit_title = f"Spotify Snapshot - {current_time}"
    stats = commit.stats
    playlist_stats = {}
    liked_songs_count = 0

    # Process playlist files and liked songs
    for changed_file in stats.files:
        if changed_file in FILENAMES.values():
            if changed_file == FILENAMES["liked_songs"]:
                file_stats = stats.files[changed_file]
                liked_songs_count = (
                    file_stats["insertions"] - 1
                    if is_first_commit
                    else file_stats["insertions"]
                )
            continue

        # This is a playlist file
        file_stats = stats.files[changed_file]
        playlist_name = changed_file.split("/")[-1].replace(".tsv", "")
        if is_first_commit:
            playlist_stats[playlist_name] = (
                file_stats["insertions"] - 1
            )  # Subtract header
        else:
            playlist_stats[playlist_name] = {
                "added": file_stats["insertions"],
                "removed": file_stats["deletions"],
            }

    commit_details = []
    if is_first_commit:
        commit_details.append(f"Liked Songs: {liked_songs_count}")
        commit_details.append(f"Number of Playlists: {len(playlist_stats)}")
        commit_details.append("\nPlaylist Details:")
        for playlist, track_count in sorted(playlist_stats.items()):
            commit_details.append(f"- {playlist}: {track_count} tracks")
    else:
        if liked_songs_count > 0:
            commit_details.append(f"Liked Songs Changes: +{liked_songs_count}")

        commit_details.append("\nPlaylist Changes:")
        has_changes = False
        for playlist, changes in sorted(playlist_stats.items()):
            if changes["added"] > 0 or changes["removed"] > 0:
                has_changes = True
                commit_details.append(
                    f"- {playlist}: +{changes['added']} -{changes['removed']}"
                )
        if not has_changes:
            commit_details.append("- None")

    commit_message_body = "\n".join(commit_details)
    return "\n\n".join([commit_title, commit_message_body])
