import os
from sys import exit

from spotify_snapshot.logging import get_colorized_logger

logger = get_colorized_logger()


def get_required_env_var(var_name: str) -> str:
    """Get an environment variable that must be set."""
    value = os.getenv(var_name)
    if not value:
        logger.error(f"Error: Missing required environment variable: {var_name}")
        logger.error("\nTo use this script, you need to set up Spotify API credentials:")
        logger.error("1. Go to https://developer.spotify.com/dashboard")
        logger.error("2. Create a new application")
        logger.error("3. Copy the Client ID and Client Secret")
        logger.error("4. Set them as environment variables:\n")
        logger.error(f"    export {var_name}=your_value_here")
        exit(1)
    return value
