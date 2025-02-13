# spotify-version-snapshots

Take snapshots of the state of your Spotify library/playlists/etc. Will
eventually be able to output these snapshots in a format understood by version
control, essentially giving you to ability to track your Spotify world as it
evolves over time.

_This code is hacky, maybe it'll be cleaned up later_

## Configuration

1. Create a spotify app at https://developer.spotify.com/dashboard/applications
2. Set the callback URL to `http://localhost:9999/callback`
3. Copy the client ID and client secret
4. Set them as environment variables:

```bash
export SPOTIFY_BACKUP_CLIENT_ID=<your-client-id>
export SPOTIFY_BACKUP_CLIENT_SECRET=<your-client-secret>
```

## Usage

```bash
python3 -m spotify_version_snapshots
```
