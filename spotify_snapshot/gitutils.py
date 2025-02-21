import git
from loguru import logger
from datetime import datetime
import os
from git import NoSuchPathError, Commit
from pathlib import Path
from spotify_snapshot import spotify
from spotify_snapshot.spotify_snapshot_output_manager import (
    SpotifySnapshotOutputManager,
)
from rich.prompt import Prompt
from .config import SpotifySnapshotConfig
from .logging import get_colorized_logger

_repo_instance = None


def get_repo_filepath(is_test_mode: bool) -> Path:
    if is_test_mode:
        return Path("/tmp/SPOTIFY-VERSION-SNAPSHOTS-TEST-REPO")

    config = SpotifySnapshotConfig.load()
    return config.backup_dir


def get_repo(is_test_mode: bool = False) -> git.Repo:
    """Get or create a singleton instance of the git repository.

    Args:
        is_test_mode: Whether to use test repository path

    Returns:
        git.Repo: Repository instance
    """
    global _repo_instance
    if _repo_instance is None:
        _repo_instance = git.Repo(get_repo_filepath(is_test_mode))
    return _repo_instance


def create_readme_if_missing(repo_filepath: Path) -> None:
    """Create a README.md file if it doesn't exist in the repository.

    Args:
        repo_filepath: Path to the git repository
    """
    logger = get_colorized_logger()
    readme_path = repo_filepath / "README.md"
    if not readme_path.exists():
        logger.info("Creating README.md file")
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(
                """# Spotify Playlist Backup

This repository contains automated backups of your Spotify playlists and liked songs, created using [spotify-snapshot](https://github.com/alichtman/spotify-snapshot).

Each playlist is stored as a TSV (Tab Separated Values) file in the `playlists` directory, and liked songs are stored in `liked_songs.tsv`.

See the [README](https://github.com/alichtman/spotify-snapshot/blob/main/README.md) for more information."""
            )
        logger.info("Created README.md file")


def setup_git_repo_if_needed(is_test_mode) -> Path:
    repo_filepath = get_repo_filepath(is_test_mode)
    logger = get_colorized_logger()
    config = SpotifySnapshotConfig.load()

    try:
        # First check if the directory exists and is a git repo
        if os.path.exists(repo_filepath) and os.path.exists(repo_filepath / ".git"):
            repo = git.Repo(repo_filepath)
            logger.info(
                f"<yellow>Found existing repo at</yellow> <green><bold>{repo_filepath}</bold></green>"
            )
            create_readme_if_missing(repo_filepath)
        else:
            raise NoSuchPathError

    except (NoSuchPathError, git.InvalidGitRepositoryError):
        if config.git_remote_url:
            try:
                logger.info(
                    f"Cloning repo from <blue>{config.git_remote_url}</blue> to <green>{str(repo_filepath).strip()}</green>"
                )
                repo = git.Repo.clone_from(config.git_remote_url, repo_filepath)
                # Set up the remote properly after cloning
                if "origin" in repo.remotes:
                    repo.delete_remote("origin")
                repo.create_remote("origin", config.git_remote_url)
            except git.GitCommandError:
                # If clone fails (e.g., empty remote), check if directory exists and is empty
                if os.path.exists(repo_filepath) and os.listdir(repo_filepath):
                    error_msg = f"Cannot create repository: Directory {repo_filepath} already exists and is not empty. You will need to manually delete it or move it to a different location."
                    logger.error(f"<red>{error_msg}</red>")
                    raise ValueError(error_msg)

                logger.info(
                    f"<yellow>Remote repo is empty. Creating new local repo at</yellow> <green><bold>{repo_filepath}</bold></green>"
                )
                os.makedirs(repo_filepath, exist_ok=True)
                git.Repo.init(repo_filepath)
        else:
            logger.info(
                f"<yellow>No repo found, making a new one at</yellow> <green><bold>{repo_filepath}</bold></green>"
            )
            os.makedirs(repo_filepath, exist_ok=True)
            git.Repo.init(repo_filepath)

    create_readme_if_missing(repo_filepath)
    return repo_filepath


def cleanup_repo():
    """Clean up the git repository instance."""
    global _repo_instance
    if _repo_instance is not None:
        _repo_instance.close()


def commit_files(is_test_mode) -> None:
    logger = get_colorized_logger()
    repo = get_repo(is_test_mode)

    is_first_commit = False
    try:
        repo.head.commit
    except ValueError:
        is_first_commit = True

    deleted_playlists = []
    if not is_first_commit:
        deleted_playlists = remove_deleted_playlists(repo, is_test_mode)

    # Check if there are any changes to commit
    if not repo.is_dirty(untracked_files=True):
        logger.info("<yellow>No changes to commit</yellow>")
        return

    repo.git.add(A=True)
    # A temp commit is needed to get stats etc - the library doesn't support it
    # otherwise
    commit = repo.index.commit("temp")
    commit_message = get_commit_message_for_amending(repo, commit, deleted_playlists)
    logger.info(
        f"<green>Commit info:</green>\n\n<yellow><bold>{commit_message}</bold></yellow>"
    )
    repo.git.commit("--amend", "-m", commit_message)
    logger.info("<green>Changes committed. All done!</green>")


def get_deleted_playlists(
    repo: git.Repo, is_test_mode: bool
) -> list[spotify.DeletedPlaylist]:
    """
    Returns a list of playlists that were deleted in the working directory changes
    """
    logger = get_colorized_logger()
    output_manager = SpotifySnapshotOutputManager.get_instance()

    # Get the working directory changes for the playlists file
    deleted_lines = []
    diff = repo.head.commit.diff(None)
    for diff_item in diff:
        # Convert both paths to strings for comparison
        if output_manager.playlists_index_filename in diff_item.a_path:
            # Read the old version of the file from the last commit
            old_content = (
                diff_item.a_blob.data_stream.read().decode("utf-8").splitlines()
            )
            # Read the current version from the working directory
            with open(output_manager.playlists_index_path, "r", encoding="utf-8") as f:
                new_content = f.read().splitlines()

            # TODO: Handle the case where the new version has no playlists

            # Find lines that were in the old content but not in the new content
            deleted_lines = [line for line in old_content if line not in new_content]
            logger.info(f"\n<red>Found {len(deleted_lines)} deleted playlists</red>")

    # Get the playlists that were deleted
    deleted_playlists = []
    for deleted_playlist in deleted_lines:
        if not deleted_playlist.strip():  # Skip empty lines
            continue
        # Get the playlist name from the first column
        playlist_name = deleted_playlist.split("\t")[0]
        # Get the playlist ID from the last column
        playlist_id = deleted_playlist.split("\t")[-1]
        deleted_playlists.append(
            spotify.DeletedPlaylist(name=playlist_name, id=playlist_id)
        )
    return deleted_playlists


def remove_deleted_playlists(
    repo: git.Repo, is_test_mode: bool
) -> list[spotify.DeletedPlaylist]:
    """
    Removes the playlists that were deleted in the staged changes
    Returns: List of deleted playlists
    """
    logger = get_colorized_logger()
    try:
        repo.head.commit  # Check if there are any commits
    except ValueError:  # No commits yet
        logger.info("<yellow>First commit detected. No playlists to delete.</yellow>")
        return []

    deleted_playlists = get_deleted_playlists(repo, is_test_mode)
    for playlist in deleted_playlists:
        file_path_to_remove = spotify.get_playlist_file_name(playlist)
        logger.info(f"<red>Deleting <bold>{file_path_to_remove}</bold></red>")
        os.remove(file_path_to_remove)
    return deleted_playlists


def get_commit_message_for_amending(
    repo: git.Repo, commit: Commit, deleted_playlists: list[spotify.DeletedPlaylist]
) -> str:
    """
    Generate a contextually appropriate commit message (depending on whether this is the first commit or not)
    If it is the first commit, the git commit is a status report on how many playlists were backed up, how many tracks per playlist, and how many liked songs were backed up
    For all commits after, the git commit is a status report on how many playlists were added, removed, and how many tracks were added, removed
    """
    output_manager = SpotifySnapshotOutputManager.get_instance()
    is_first_commit = len(commit.parents) == 0
    current_time = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
    if is_first_commit:
        commit_title = f"Initial Spotify Snapshot - {current_time}"
    else:
        commit_title = f"Spotify Snapshot - {current_time}"
    stats = commit.stats
    playlist_stats = {}
    liked_songs_add_remove_stats = None

    # Process playlist files and liked songs
    for changed_file in stats.files:
        # print(f"changed_file: {changed_file}")
        if (output_manager.liked_songs_filename) != changed_file:
            continue

        file_stats = stats.files[changed_file]
        if is_first_commit:
            liked_songs_add_remove_stats = (
                file_stats["insertions"] - 1
            )  # Subtract header
        else:
            liked_songs_add_remove_stats = {
                "added": file_stats["insertions"],
                "removed": file_stats["deletions"],
            }

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

    # If liked songs file is present, grab the count of tracks
    liked_songs_count = None
    liked_songs_file = output_manager.liked_songs_path
    if os.path.exists(liked_songs_file):
        with open(liked_songs_file, "r", encoding="utf-8") as f:
            liked_songs_count = len(f.readlines()) - 1

    commit_details = []
    # Always add Liked Songs section first if there is a liked songs file in the backup
    if liked_songs_add_remove_stats is not None:
        commit_details.append(f"Liked Songs        : {liked_songs_count} tracks")

        if not is_first_commit:
            commit_details.append(
                f"Liked Songs Changes: +{liked_songs_add_remove_stats['added']}, -{liked_songs_add_remove_stats['removed']}"
            )

    if is_first_commit:
        commit_details.append(f"Number of Playlists: {len(playlist_stats)}")
        commit_details.append("\nPlaylist Details:")
        for playlist, track_count in sorted(playlist_stats.items()):
            commit_details.append(f"- {playlist}: {track_count} tracks")
    else:
        # Add detection of renamed playlists
        renamed_playlists = []
        renamed_playlist_ids = set()  # Track IDs of renamed playlists

        # Compare with parent commit to get changes
        for diff_item in commit.diff(commit.parents[0] if commit.parents else None):
            if diff_item.renamed_file and diff_item.a_path.startswith("playlists/"):
                # Extract everything before the last parenthetical for both old and new names
                old_name = diff_item.a_path.split("/")[-1].rsplit(" (", 1)[0]
                new_name = diff_item.b_path.split("/")[-1].rsplit(" (", 1)[0]
                # Extract playlist ID from the filename
                playlist_id = diff_item.a_path.rsplit("(", 1)[-1].rstrip(").tsv")
                renamed_playlists.append((old_name, new_name))
                renamed_playlist_ids.add(playlist_id)

        # Filter out renamed playlists from deleted_playlists
        filtered_deleted_playlists = [
            playlist
            for playlist in deleted_playlists
            if playlist.id not in renamed_playlist_ids
        ]

        # Compare with parent commit to get changes
        created_playlists = []
        for diff_item in commit.diff(commit.parents[0] if commit.parents else None):
            if (
                not diff_item.renamed_file
                and diff_item.new_file
                and diff_item.b_path.startswith("playlists/")
            ):
                # Extract everything before the last parenthetical (which contains the ID)
                playlist_name = diff_item.b_path.split("/")[-1].rsplit(" (", 1)[0]
                created_playlists.append(playlist_name)

        if created_playlists:
            commit_details.append("\nCreated Playlists:")
            for playlist in created_playlists:
                commit_details.append(f"- {playlist}")

        if filtered_deleted_playlists:
            commit_details.append("\nDeleted Playlists:")
            for playlist in filtered_deleted_playlists:
                commit_details.append(f"- {playlist.name}")

        if renamed_playlists:
            commit_details.append("\nRenamed Playlists:")
            for old_name, new_name in renamed_playlists:
                commit_details.append(f"- {old_name} → {new_name}")

        commit_details.append("\nChanged Playlists:")
        has_changes = False
        for playlist, changes in sorted(playlist_stats.items()):
            if changes["added"] > 0 or changes["removed"] > 0:
                has_changes = True
                commit_details.append(
                    f"- {playlist}: +{changes['added']} -{changes['removed']}"
                )
        if not has_changes:
            commit_details.pop()

    commit_message_body = "\n".join(commit_details)
    return "\n\n".join([commit_title, commit_message_body])


def set_remote_url(url: str, is_test_mode: bool) -> None:
    """Set the remote URL for the git repository.

    Args:
        url: Git remote URL
        is_test_mode: Whether to use test repository path
    """
    repo = get_repo(is_test_mode)
    try:
        remote = repo.remote("origin")
        remote.set_url(url)
    except ValueError:
        # Remote doesn't exist, create it
        repo.create_remote("origin", url)


def maybe_git_push(
    is_test_mode: bool, should_push_without_prompting_user: bool = False
) -> None:
    """Push changes to the remote repository.

    Args:
        is_test_mode: Whether running in test mode
        should_prompt_user: If True, prompts the user to confirm the push
    """
    logger = get_colorized_logger()
    repo = get_repo(is_test_mode)

    # Check if remote exists and has a URL configured
    try:
        remote = repo.remote("origin")
        if not remote.urls:
            logger.warning("No remote URL configured. Skipping push.")
            return
    except ValueError:
        logger.warning("No remote configured. Skipping push.")
        return

    should_push = False
    if not should_push_without_prompting_user:
        response = Prompt.ask(
            "\nPush changes to remote repository?", choices=["y", "N"], default="N"
        )
        should_push = response == "y"

    if should_push:
        try:
            logger.info("Pushing changes to remote...")
            # Check if we're on a branch
            if repo.head.is_detached:
                error_msg = "Cannot push: HEAD is in a detached state. Please checkout a branch first."
                logger.error(error_msg)
                exit(1)
                # # Get available branches
                # branches = [b.name for b in repo.heads]
                # if not branches:
                #     logger.error("No branches available to checkout")
                #     return

                # # Format branch choices for prompt
                # branch_choices = [str(i) for i in range(len(branches))]
                # branch_list = "\n".join(f"{i}: {b}" for i, b in enumerate(branches))

                # logger.info(f"\nAvailable branches:\n{branch_list}")
                # choice = Prompt.ask(
                #     "\nSelect a branch to checkout", choices=branch_choices, default="0"
                # )

                # # Checkout selected branch
                # selected_branch = branches[int(choice)]
                # repo.heads[selected_branch].checkout()
                # logger.info(f"Checked out branch: {selected_branch}")

            repo.remotes.origin.push()
            # Convert SSH URL to HTTPS URL if needed
            url = repo.remotes.origin.url
            if url.startswith("git@"):
                # Convert git@github.com:user/repo.git to https://github.com/user/repo
                url = url.replace(":", "/").replace("git@", "https://").rstrip(".git")
            success_msg = f"Successfully pushed changes to {url}!"
            logger.info(success_msg)
        except git.GitCommandError as e:
            error_msg = f"Failed to push changes: {str(e)}"
            logger.error(error_msg)
            logger.error(f"Git command failed with exit code {e.status}")
            logger.error(f"Git stderr: {e.stderr}")
            logger.error(f"[red]{error_msg}[/red]")
