import requests
import json
from datetime import datetime, timedelta, timezone
import time
import logging
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

with open('config.json', 'r') as config_file:
    config = json.load(config_file)

webevent_url = config['webevent_url']
Drago_url = config['Drago_url']
AREA_IDS = config['area_ids']
SLEEP_TIME = config['sleep_time']
RESCAN_WINDOW_MINUTES = config['rescan_window_minutes']
DISCORD_WEBHOOK_URL = config['discord_webhook_url']
rescan_community_day = config.get('rescan_community_day', True)

def fetch_and_update_events():
    try:
        response = requests.get(webevent_url)
        response.raise_for_status()
        remote_events = response.json()

        local_events = load_existing_events()
        if not isinstance(local_events, list):
            logger.error("Local events data is missing or corrupted. Initializing with an empty list.")

        local_events = []
        now = datetime.utcnow().replace(tzinfo=timezone.utc)

        new_events = []
        for event in remote_events:
            start_date_str = event.get('start')
            if not start_date_str:
                logger.info(f"Skipping event '{event['name']}' because the start date is missing.")
                continue

            start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00')).astimezone(timezone.utc)
            if start_date + timedelta(minutes=RESCAN_WINDOW_MINUTES) < now:
                logger.info(f"Skipping event '{event['name']}' because it is in the past.")
                continue

            if (event['extraData']['generic'].get('hasFieldResearchTasks') and
                event['eventID'] not in {e['eventID'] for e in local_events}):

                new_events.append({
                    'eventID': event['eventID'],
                    'name': event['name'],
                    'start': event['start'],
                    'end': event['end'],
                    'extraData': event['extraData'],
                    'rescan_triggered': False
                })

        if new_events:
            local_events.extend(new_events)
            save_events(local_events)
            send_discord_notification(new_events, "new_event")
            logger.info(f"{len(new_events)} new events added.")
        else:
            logger.info("No new events found.")
    except Exception as e:
        logger.error(f"Error fetching and updating events: {e}")

def load_existing_events():
    if os.path.exists('events.json'):
        with open('events.json', 'r') as file:
            try:
                return json.load(file) or []  # Ensure an empty list is returned if file is empty
            except json.JSONDecodeError:
                logger.warning("events.json is empty or corrupted. Initializing with an empty list.")
                return []
    return []

def save_events(events):
    with open('events.json', 'w') as file:
        json.dump(events, file, indent=4)

def start_rescan(event):
    try:
        event_name = event['name']
        if AREA_IDS == "all":
            post_url = f"{Drago_url}/quest/all/start"
            response = requests.get(post_url)
            response.raise_for_status()
            logger.info(f"Rescan GET request sent for '{event_name}' to URL: {post_url}. Response: {response.status_code}")
        else:
            for area_id in AREA_IDS:
                post_url = f"{Drago_url}/quest/{area_id}/start"
                response = requests.get(post_url)
                response.raise_for_status()
                logger.info(f"Rescan GET request sent for '{event_name}' to URL: {post_url}. Response: {response.status_code}")
        send_discord_notification([event], "rescan_triggered")
    except Exception as e:
        logger.error(f"Error sending rescan GET request for event '{event_name}': {e}")

def check_and_trigger_rescan():
    try:
        now = datetime.now(timezone.utc)
        local_events = load_existing_events()
        events_updated = False

        for event in local_events:
            start_time = datetime.fromisoformat(event['start'].replace('Z', '+00:00')).astimezone(timezone.utc)
            if (now >= start_time and
                now <= start_time + timedelta(minutes=RESCAN_WINDOW_MINUTES) and
                not event['rescan_triggered']):

                if "Community Day" in event['name'] and not rescan_community_day:
                    logger.info(f"Skipping rescan for '{event['name']}' due to Community Day setting.")
                    continue

                logger.info(f"Event '{event['name']}' started recently. Triggering rescan.")
                start_rescan(event)

                event['rescan_triggered'] = True
                events_updated = True

        if events_updated:
            save_events(local_events)
    except Exception as e:
        logger.error(f"Error checking and triggering rescan: {e}")

def remove_expired_events():
    try:
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        local_events = load_existing_events()
        updated_events = []

        for event in local_events:
            end_time = datetime.fromisoformat(event['end'].replace('Z', '+00:00')).astimezone(timezone.utc)
            if now <= end_time + timedelta(days=1):
                updated_events.append(event)
            else:
                logger.info(f"Removing expired event '{event['name']}' as it ended more than a day ago.")

        if len(updated_events) != len(local_events):
            save_events(updated_events)
        else:
            logger.info("No expired events found to remove.")
    except Exception as e:
        logger.error(f"Error removing expired events: {e}")

def send_discord_notification(events, message_type="new_event"):
    
    if not DISCORD_WEBHOOK_URL:
        logger.info("Discord Webhook URL is not set. Skipping Discord notification.")
        return

    if message_type == "new_event":
        message = "**New Event(s) Added**\n\n"
    elif message_type == "rescan_triggered":
        message = "**Rescan Triggered**\n\n"
    else:
        message = "**Event Notification**\n\n"

    sorted_events = sorted(events, key=lambda event: datetime.fromisoformat(event['start'].replace('Z', '+00:00')).astimezone(timezone.utc))

    for event in sorted_events:
        message += (
            f"**Event: {event['name']}**\n"
            f"**Time**: `{event['start']}` - `{event['end']}`\n"
            "\n"
        )

    try:
        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json={"content": message},
            headers={"Content-Type": "application/json"}
        )
        if response.status_code == 204:
            logger.info("Discord notification sent successfully.")
        else:
            logger.error(f"Failed to send Discord notification: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Error sending Discord notification: {e}")


def main_loop():
    while True:
        logger.info("Starting event check and update cycle.")
        fetch_and_update_events()
        check_and_trigger_rescan()
        remove_expired_events()

        logger.info(f"Sleeping for {SLEEP_TIME} seconds.")
        time.sleep(SLEEP_TIME)

if __name__ == "__main__":
    main_loop()