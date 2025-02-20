import os


def get_required_env_var(var_name: str) -> str:
    """Get an environment variable that must be set."""
    value = os.getenv(var_name)
    if not value:
        print(f"Error: Missing required environment variable: {var_name}")
        print("\nTo use this script, you need to set up Spotify API credentials:")
        print("1. Go to https://developer.spotify.com/dashboard")
        print("2. Create a new application")
        print("3. Copy the Client ID and Client Secret")
        print("4. Set them as environment variables:\n")
        print(f"    export {var_name}=your_value_here")
        exit(1)
    return value
