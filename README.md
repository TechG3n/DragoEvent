# Simple Tool to Fetch Events and Start a Quest Rescan

This tool monitors events from a remote source and triggers a quest rescan when qualifying events start. <br> 
Notifications can also be sent to a Discord webhook for new events and rescans.

### Setup

1. **Copy** `config.json.example` to `config.json` and fill in the details:
   - **webevent_url:** The URL for fetching remote events.
   - **Drago_url:** The base URL to trigger rescans.
   - **area_ids:** Use an array of IDs `["123", "456", "789"]` for specific areas, or set to `"all"` for all areas.
   - **rescan_community_day:** Set to `true` to allow rescans on Community Days, or `false` to skip them.
   - **sleep_time**: Sleep in seconds between fetching and checking events
   - **rescan_window_minutes:** Set timeframe in minutes in which a event is triggering a restart, Should be at least double the sleep time
   - **discord_webhook_url:** Channel in which updates should be posted

2. **Install required packages:**

   ```bash
   pip install -r requirements.txt

   (If needed, use venv to seperate from toher projects)

3. **Run the script:**

   ```
   python3 events.py

   (Use a process manager like pm2 or supervisor to keep it running continuously.)