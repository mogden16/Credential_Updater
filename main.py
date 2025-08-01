import requests
from datetime import datetime, timedelta
import time
import os
import re
import config

# Discord webhook URL used for sending notifications
WEBHOOK_URL = config.DISCORD_WEBHOOK_URL

# Bot token and channel for reading messages
BOT_TOKEN = config.DISCORD_BOT_TOKEN
CHANNEL_ID = config.DISCORD_CHANNEL_ID

# File to store PMP PDU count
PDU_FILE = 'pmp_pdu_count.txt'
# File to track the last processed Discord message
LAST_MESSAGE_FILE = 'last_message_id.txt'
# File to store logged PE EDU entries
PE_EDU_LOG = 'pe_edu_log.csv'

# Certification data
CERTIFICATIONS = [
    {
        'name': 'PMP',
        'renewal_date': '2027-08-24',
        'total_pdus': 60,
        'tracks_pdus': True
    },
    {
        'name': 'PE',
        'renewal_date': '2027-09-30',
        'tracks_pdus': False
    },
    {
        'name': 'CEM',
        'renewal_date': '2027-12-31',
        'tracks_pdus': False
    }
]


def load_pdu_count():
    """Load the PMP PDU count from a file or initialize it."""
    if os.path.exists(PDU_FILE):
        with open(PDU_FILE, 'r') as file:
            try:
                return int(file.read().strip())
            except ValueError:
                return 2  # Default to 2 if the file is corrupted
    return 2  # Default starting PDUs


def save_pdu_count(pdu_count):
    """Save the current PMP PDU count to a file."""
    with open(PDU_FILE, 'w') as file:
        file.write(str(pdu_count))


def load_last_message_id():
    """Load the last processed Discord message ID."""
    if os.path.exists(LAST_MESSAGE_FILE):
        with open(LAST_MESSAGE_FILE, 'r') as file:
            return file.read().strip() or None
    return None


def save_last_message_id(message_id):
    """Persist the last processed Discord message ID."""
    with open(LAST_MESSAGE_FILE, 'w') as file:
        file.write(str(message_id))


def fetch_new_discord_messages():
    """Return new Discord messages since the last processed ID."""
    last_id = load_last_message_id()
    url = f'https://discord.com/api/v10/channels/{CHANNEL_ID}/messages'
    params = {'limit': 50}
    if last_id:
        params['after'] = last_id

    headers = {'Authorization': f'Bot {BOT_TOKEN}'}
    resp = requests.get(url, headers=headers, params=params)
    if resp.status_code != 200:
        print(f'Failed to fetch Discord messages: {resp.status_code}')
        return []

    messages = sorted(resp.json(), key=lambda m: int(m['id']))
    if messages:
        save_last_message_id(messages[-1]['id'])
    return messages


def check_discord_messages_for_pdu(messages, current_pdu):
    """Scan Discord messages for PDU updates and adjust the count."""
    for msg in messages:
        content = msg.get('content', '').lower()
        match = re.search(r'added\s+(\d+)\s+pdu', content)
        if match and 'pmp' in content:
            added = int(match.group(1))
            current_pdu += added
            print(f'Detected PDU update from Discord: +{added} PDUs (now {current_pdu})')
    return current_pdu


def check_discord_messages_for_pe_edu(messages):
    """Log PE EDU entries found in Discord messages.

    Expected message format:
        PE EDU: <topic> - <hours> hours - <YYYY-MM-DD>

    Example:
        PE EDU: Ethics Course - 1.5 hours - 2024-05-01
    """
    for msg in messages:
        content = msg.get('content', '')
        match = re.search(r'pe edu:\s*(.+?)\s*-\s*(\d+(?:\.\d+)?)\s*hours?\s*-\s*(\d{4}-\d{2}-\d{2})', content, re.I)
        if match:
            topic, hours, date_str = match.groups()
            with open(PE_EDU_LOG, 'a') as log:
                log.write(f'{date_str},{hours},{topic}\n')
            print(f'Logged PE EDU from Discord: {topic} - {hours} hours on {date_str}')


def prompt_for_pdu_count(current_pdu):
    """Prompt the user for the current PMP PDU count and update if valid input is given."""
    print(f'Current PMP PDUs: {current_pdu}/{CERTIFICATIONS[0]["total_pdus"]}')
    user_input = input('Enter your current number of PMP PDUs (or any text to keep the same): ').strip()
    if user_input.isdigit():
        new_pdu = int(user_input)
        print(f'Updated PMP PDUs to {new_pdu}.')
        return new_pdu
    else:
        print('Keeping the current PMP PDU count.')
        return current_pdu


def send_discord_alert(cert_name, days_left, renewal_date, current_pdu=None, total_pdus=None):
    """Send a notification to Discord with details for each certification."""
    if current_pdu is not None and total_pdus is not None:
        pdus_needed = total_pdus - current_pdu
        message = (
            f'🔔 Reminder: Your **{cert_name}** certification expires in **{days_left} days** (Deadline: {renewal_date}).\n'
            f'You currently have **{current_pdu}/{total_pdus} PDUs**. You need **{pdus_needed} more PDUs** to renew.'
        )
    else:
        message = f'🔔 Reminder: Your **{cert_name}** certification expires in **{days_left} days** (Deadline: {renewal_date}).'

    payload = {'content': message}
    response = requests.post(WEBHOOK_URL, json=payload)

    if response.status_code == 204:
        print(f'Successfully sent reminder for {cert_name}.')
    else:
        print(f'Failed to send reminder for {cert_name}. Status code: {response.status_code}')


def check_certifications():
    """Check all certifications and send reminders."""
    today = datetime.today()
    current_pdu = load_pdu_count()
    messages = fetch_new_discord_messages()
    current_pdu = check_discord_messages_for_pdu(messages, current_pdu)
    check_discord_messages_for_pe_edu(messages)

    for cert in CERTIFICATIONS:
        renewal_date = datetime.strptime(cert['renewal_date'], '%Y-%m-%d')
        days_left = (renewal_date - today).days

        if cert['tracks_pdus']:
            send_discord_alert(cert['name'], days_left, cert['renewal_date'], current_pdu, cert['total_pdus'])
        else:
            send_discord_alert(cert['name'], days_left, cert['renewal_date'])

    # Prompt for PMP PDU update
    new_pdu = prompt_for_pdu_count(current_pdu)
    save_pdu_count(new_pdu)


if __name__ == '__main__':
    while True:
        # Run the check immediately
        check_certifications()
        # Wait 30 days before checking again
        time.sleep(30 * 86400)
