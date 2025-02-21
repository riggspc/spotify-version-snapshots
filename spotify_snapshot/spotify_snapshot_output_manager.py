from pathlib import Path
from typing import Optional
from loguru import logger
from spotify_snapshot.logging import get_colorized_logger


class SpotifySnapshotOutputManager:
    _instance: Optional["SpotifySnapshotOutputManager"] = None

    def __init__(self, base_dir: Path | str = Path(".")):
        if SpotifySnapshotOutputManager._instance is not None:
            raise RuntimeError(
                "Use SpotifySnapshotOutputManager.initialize() or get_instance()"
            )
        self.base_dir = Path(base_dir)
        self.ensure_output_dirs()

    @classmethod
    def initialize(
        cls, base_dir: Path | str = Path(".")
    ) -> "SpotifySnapshotOutputManager":
        if cls._instance is None:
            cls._instance = cls(base_dir)
        return cls._instance

    @classmethod
    def get_instance(cls) -> "SpotifySnapshotOutputManager":
        if cls._instance is None:
            raise RuntimeError(
                "SpotifySnapshotOutputManager not initialized. Call initialize() first"
            )
        return cls._instance

    @property
    def liked_songs_filename(self) -> str:
        """Filename for liked songs file"""
        return "liked_songs.tsv"

    @property
    def albums_filename(self) -> str:
        """Filename for saved albums file"""
        return "saved_albums.tsv"

    @property
    def playlists_index_filename(self) -> str:
        """Filename for playlists index file"""
        return "playlists.tsv"

    @property
    def liked_songs_path(self) -> Path:
        """Full path to liked songs file"""
        return self.base_dir / self.liked_songs_filename

    @property
    def albums_path(self) -> Path:
        """Full path to saved albums file"""
        return self.base_dir / self.albums_filename

    @property
    def playlists_index_path(self) -> Path:
        """Full path to playlists index file"""
        return self.base_dir / self.playlists_index_filename

    @property
    def playlists_dir_path(self) -> Path:
        return self.base_dir / "playlists"

    def ensure_output_dirs(self) -> None:
        """Ensure all output directories exist"""
        logger = get_colorized_logger()
        if not self.base_dir.exists():
            logger.info(
                f"<blue>Creating directory</blue> <green><bold>{self.base_dir}</bold></green>"
            )
            self.base_dir.mkdir(parents=True, exist_ok=True)

        if not self.playlists_dir_path.exists():
            logger.info(
                f"<blue>Creating directory</blue> <green><bold>{self.playlists_dir_path}</bold></green>"
            )
            self.playlists_dir_path.mkdir(parents=True, exist_ok=True)
