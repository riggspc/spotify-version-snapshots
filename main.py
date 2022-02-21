import spotipy
import time
from spotipy.oauth2 import SpotifyOAuth
from credentials import CLIENT_ID, CLIENT_SECRET

# General TODOs:
# - Error handling

sp = spotipy.Spotify(
    auth_manager=SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri="http://localhost:8888/callback",
        scope="user-library-read",
    )
)

# Can only get 50 tracks at a time, iterate through the library until we've
# got them all. Use a dict to avoid duplicating tracks if the library is added
# to while we're fetching it
limit = 50
offset = 0
saved_tracks = {}
while True:
    results = sp.current_user_saved_tracks(limit=limit, offset=offset)
    result_items = results["items"]
    print(f"Fetched {len(result_items)} items")
    for item in result_items:
        saved_tracks[item['track']['id']] = item
    if len(result_items) is not limit:
        break
    offset += limit
    # Prevent rate limiting. Maybe not needed, playing it safely for now
    time.sleep(0.5)

print(len(saved_tracks))
