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

def fetch_and_update_events():
    try:
        response = requests.get(webevent_url)
        response.raise_for_status()
        remote_events = response.json()

        local_events = load_existing_events()
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
            logger.info(f"{len(new_events)} new events added.")
        else:
            logger.info("No new events found.")
    except Exception as e:
        logger.error(f"Error fetching and updating events: {e}")

def load_existing_events():
    if os.path.exists('events.json'):
        with open('events.json', 'r') as file:
            return json.load(file)
    return []

def save_events(events):
    with open('events.json', 'w') as file:
        json.dump(events, file, indent=4)

def send_rescan_post_request(event_name):
    try:
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
    except Exception as e:
        logger.error(f"Error sending rescan GET request for event '{event_name}': {e}")

def check_and_trigger_rescan():
    try:
        now = datetime.now(timezone.utc)
        local_events = load_existing_events()
        events_updated = False

        for event in local_events:
            start_time = datetime.fromisoformat(event['start'].replace('Z', '+00:00')).astimezone(timezone.utc)
            #logger.info(f"Event: {event['name']} Start: {start_time} now: {now} delta: {delta}")
            if (now >= start_time and
                now <= start_time + timedelta(minutes=RESCAN_WINDOW_MINUTES) and
                not event['rescan_triggered']):

                if "Community Day" in event['name'] and not config.get('rescan_community_day', True):
                    logger.info(f"Skipping rescan for '{event['name']}' due to Community Day setting.")
                    continue

                logger.info(f"Event '{event['name']}' started recently. Triggering rescan.")
                send_rescan_post_request(event['name'])

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
