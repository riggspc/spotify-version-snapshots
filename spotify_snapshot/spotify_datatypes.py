from dataclasses import dataclass


@dataclass
class SpotifyImage:
    height: int | None
    width: int | None
    url: str


@dataclass
class SpotifyUser:
    display_name: str
    external_urls: dict[str, str]
    href: str
    id: str
    type: str
    uri: str


@dataclass
class SpotifyTracks:
    href: str
    total: int


@dataclass
class SpotifyPlaylist:
    collaborative: bool
    description: str
    external_urls: dict[str, str]
    href: str
    id: str
    images: list[SpotifyImage]
    name: str
    owner: SpotifyUser
    primary_color: str | None
    public: bool
    snapshot_id: str
    tracks: SpotifyTracks
    type: str
    uri: str


@dataclass
class SpotifyAlbum:
    name: str
    id: str


@dataclass
class SpotifyArtist:
    name: str


@dataclass
class SpotifyTrack:
    album: SpotifyAlbum
    artists: list[SpotifyArtist]
    name: str
    id: str


@dataclass
class SpotifyAddedBy:
    id: str


@dataclass
class SpotifyPlaylistTrackItem:
    track: SpotifyTrack
    added_by: SpotifyAddedBy
    added_at: str


@dataclass
class SpotifyPlaylistTracksResponse:
    items: list[SpotifyPlaylistTrackItem]
    next: str | None
    total: int


@dataclass
class SpotifyPlaylistsResponse:
    items: list[SpotifyPlaylist]
    next: str | None
    total: int


@dataclass
class DeletedPlaylist:
    name: str
    id: str
