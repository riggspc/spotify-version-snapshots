# `spotify-snapshot`

Easily snapshot the state of your `Spotify` library/playlists/etc, and store it in version control.

If Spotify ever disappears, you'll have a backup of your music library. And you'll have the ability to track your Spotify world as it evolves over time.

## Configuration

1. Create a `Spotify` app at https://developer.spotify.com/dashboard/applications
2. Set the callback URL to `http://localhost:9999/callback`
3. Copy the client ID and client secret
4. Set them as environment variables:

```bash
export SPOTIFY_BACKUP_CLIENT_ID=<your-client-id>
export SPOTIFY_BACKUP_CLIENT_SECRET=<your-client-secret>
```

## Usage

```bash
$ git clone git@github.com:alichtman/spotify-snapshot.git
$ cd spotify-snapshot
$ python3 -m spotify_snapshot
```

### Automated Backups

You can set up automatic backups that run every 8 hours using the built-in cronjob integration:

```bash
$ spotify-snapshot --install
```

This will:

- Install a cronjob that runs every 8 hours
- Run in production mode (equivalent to `--prod-run`)
- Backup your entire library (liked songs, saved albums, and playlists)

To manually check when the next backup will run:

```bash
$ crontab -l | grep spotify-snapshot
```

> TODO: Upload to pypi
