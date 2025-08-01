import requests
from datetime import datetime, timedelta
import time
import os
import config

# Discord webhook URL (replace with your webhook URL)
WEBHOOK_URL = config.DISCORD_WEBHOOK_URL

# File to store PMP PDU count
PDU_FILE = 'pmp_pdu_count.txt'

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
