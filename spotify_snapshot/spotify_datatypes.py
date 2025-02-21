from dataclasses import dataclass
from typing import List, Optional, Dict


@dataclass
class SpotifyImage:
    height: Optional[int]
    width: Optional[int]
    url: str


@dataclass
class SpotifyUser:
    display_name: str
    external_urls: Dict[str, str]
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
    external_urls: Dict[str, str]
    href: str
    id: str
    images: List[SpotifyImage]
    name: str
    owner: SpotifyUser
    primary_color: Optional[str]
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
    artists: List[SpotifyArtist]
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
    items: List[SpotifyPlaylistTrackItem]
    next: Optional[str]
    total: int


@dataclass
class SpotifyPlaylistsResponse:
    items: List[SpotifyPlaylist]
    next: Optional[str]
    total: int


@dataclass
class DeletedPlaylist:
    name: str
    id: str 