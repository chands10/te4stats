# te4stats

Process head to head stats from the game Tennis Elbow 4

Can also run in Discord DMs via command `/getstats`, which contains an optional argument for how many matches to upload full stats for as images (default 1).

Need to set some environment variables (can use .env file):
- `DISCORD_API`: Discord token (if running bot.py)
- `MATCH_LOG`: File location of TE4 match log
- `PLAYER_ONE`: ", " separated list of all names for player one
- `PLAYER_TWO`: ", " separated list of all names for player two
