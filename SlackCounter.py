import os
import time
import sqlite3
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from collections import defaultdict
from datetime import datetime
import argparse
import csv
from tqdm import tqdm

# Params
client = WebClient(token='INSERT-TOKEN-HERE')  # ideally pull securely

default_csv_name = "SlackCounter.csv"
size_of_list = 25
rate_limit_in_seconds = 1
database = 'slack_reactions.db'
verbose = False
csv_flag = False

emoticon_string = None
pull_int = None
output_order = True


class SlackRateLimiter:
    def __init__(self, rate_limit_in_seconds):
        self.rate_limit_in_seconds = rate_limit_in_seconds
        self.last_request_time = None

    def rate_limit(self):
        if self.last_request_time is not None:
            elapsed_time = time.time() - self.last_request_time
            if elapsed_time < self.rate_limit_in_seconds:
                time.sleep(self.rate_limit_in_seconds - elapsed_time)
        self.last_request_time = time.time()

rate_limiter = SlackRateLimiter(rate_limit_in_seconds)

#### Database Setup & Interactions
def initialize_database():
    conn = sqlite3.connect(database)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reactions (
            message_id TEXT,
            user_id TEXT,
            reaction TEXT,
            count INTEGER,
            date TEXT,
            PRIMARY KEY (message_id, user_id, reaction)
        )
    ''')
    conn.commit()
    conn.close()
    if verbose:
        print("Database initialized...")

def insert_reaction(message_id, user_id, reaction, count, date):
    conn = sqlite3.connect(database)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO reactions (message_id, user_id, reaction, count, date)
        VALUES (?, ?, ?, ?, ?)
    ''', (message_id, user_id, reaction, count, date))
    conn.commit()
    conn.close()

def check_reaction_exists(message_id, user_id, reaction):
    conn = sqlite3.connect(database)
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM reactions WHERE message_id = ? AND user_id = ? AND reaction = ?', (message_id, user_id, reaction))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def get_most_recent_reaction_date(emoticon):
    conn = sqlite3.connect(database)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT MAX(date) 
        FROM reactions 
        WHERE reaction = ?
    ''', (emoticon,))
    recent_date = cursor.fetchone()[0]
    conn.close()
    return recent_date

def get_user_reactions(emoticon):
    conn = sqlite3.connect(database)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT user_id, SUM(count) 
        FROM reactions 
        WHERE reaction = ? 
        GROUP BY user_id
    ''', (emoticon,))
    reactions = cursor.fetchall()
    conn.close()
    return reactions

#### Slack API Helper Funcs

def get_user_info(user_id):
    try:
        response = client.users_info(user=user_id)
        return response['user']
    except SlackApiError as e:
        if verbose:
            print(f"Error fetching user info for {user_id}: {e.response['error']}")
        return None

def get_user_names(user_ids):
    user_names = {}
    for user_id in user_ids:
        try:
            response = client.users_info(user=user_id)
            user_names[user_id] = response['user']['real_name']
        except SlackApiError as e:
            if verbose:
                print(f"Error fetching user info for {user_id}: {e.response['error']}")
            user_names[user_id] = "Unknown User"
    return user_names

def get_channels():
    try:
        response = client.conversations_list()
        channels = response['channels']
        return [(channel['id'], channel['name']) for channel in channels]
    except SlackApiError as e:
        if verbose:
            print(f"Error fetching channels: {e.response['error']}")
        return []

def get_all_messages(channel_id, channel_name):
    try:
        rate_limiter.rate_limit()
        messages = []
        cursor = None
        while True:
            response = client.conversations_history(channel=channel_id, cursor=cursor)
            messages.extend(response['messages'])
            if not response['has_more']:
                break
            cursor = response['response_metadata']['next_cursor']
        return messages
    except SlackApiError as e:
        if verbose:
            print(f"Error fetching messages from channel {channel_name} (ID: {channel_id}): {e.response['error']}")
        return []

def get_thread_messages(channel_id, thread_ts):
    try:
        rate_limiter.rate_limit()
        messages = []
        cursor = None
        while True:
            response = client.conversations_replies(channel=channel_id, ts=thread_ts, cursor=cursor)
            messages.extend(response['messages'])
            if not response['has_more']:
                break
            cursor = response['response_metadata']['next_cursor']
        return messages
    except SlackApiError as e:
        if verbose:
            print(f"Error fetching messages in thread {thread_ts} from channel {channel_id}: {e.response['error']}")
        return []

def get_channel_members(channel_id):
    try:
        response = client.conversations_members(channel=channel_id)
        return response['members']
    except SlackApiError as e:
        if verbose:
            print(f"Error fetching members for channel {channel_id}: {e.response['error']}")
        return []

#### Count Functions

def count_emoticon_reactions(emoticon):
    channels = get_channels()
    user_reactions = defaultdict(int)

    # Initialize the progress bar
    total_channels = len(channels)
    with tqdm(total=total_channels, desc="Processing Channels") as pbar:
        if verbose:
            print("\n")
        for channel_id, channel_name in channels:
            users = get_channel_members(channel_id)
            messages = get_all_messages(channel_id, channel_name)
            for message in messages:
                message_date = datetime.fromtimestamp(float(message['ts'])).strftime('%Y-%m-%d')
                if 'reactions' in message:
                    for reaction in message['reactions']:
                        if reaction['name'] == emoticon:
                            if verbose:
                                print(f"Inserting reaction: {message['ts']}, {message['user']}, {reaction['name']}, {reaction['count']}, {message_date}")
                            insert_reaction(message['ts'], message['user'], reaction['name'], reaction['count'], message_date)
                            user_reactions[message['user']] += reaction['count']

                if 'thread_ts' in message:
                    thread_messages = get_thread_messages(channel_id, message['thread_ts'])
                    for thread_message in thread_messages:
                        thread_message_date = datetime.fromtimestamp(float(thread_message['ts'])).strftime('%Y-%m-%d')
                        if 'reactions' in thread_message:
                            for reaction in thread_message['reactions']:
                                if reaction['name'] == emoticon:
                                    if verbose:
                                        print(f"Inserting thread reaction: {thread_message['ts']}, {thread_message['user']}, {reaction['name']}, {reaction['count']}, {thread_message_date}")
                                    insert_reaction(thread_message['ts'], thread_message['user'], reaction['name'], reaction['count'], thread_message_date)
                                    user_reactions[thread_message['user']] += reaction['count']

            pbar.update(1)  # Update the progress bar after processing each channel
            if verbose:
                print("\n")
    return user_reactions

# User Helper Funcs

def print_database(database):
    # Display contents of the database for verification
    conn = sqlite3.connect(database)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM reactions')
    rows = cursor.fetchall()
    if verbose:
        print("Database contents:")
        for row in rows:
            print(row)
    conn.close()

def print_top_users(user_reactions, emoticon, csv_file=None):
    sorted_reactions = sorted(user_reactions, key=lambda x: x[1], reverse=output_order)
    top_users = sorted_reactions[:size_of_list]

    user_ids = [user for user, count in top_users]
    user_names = get_user_names(user_ids)

    print(f"\nTop users who received '{emoticon}' reaction:\n")
    for user, count in top_users:
        print(f"{user_names[user]}: {count} reaction(s)")
    print("\n")
    
    if csv_flag:
        # Determine the CSV file path
        if csv_file is None:
            csv_file = "SlackCounter.csv"

        # Write the user list to the CSV file
        with open(csv_file, 'w', newline='') as csvfile:
            fieldnames = ['User ID', 'User Name', 'Reaction Count']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for user, count in top_users:
                writer.writerow({'User ID': user, 'User Name': user_names[user], 'Reaction Count': count})
   
def get_emoticon_from_user():
    if emoticon_string is not None:
        emoticon = emoticon_string
    else:
        emoticon = input("Enter the emoticon to scan for (without colons, e.g., '+1'): ")
    return emoticon

def pull_data_option(emoticon):
    recent_date = get_most_recent_reaction_date(emoticon)
    if verbose:
        if recent_date:
            print(f"The most recent timestamp in database for the emoticon '{emoticon}' is: {recent_date}")
        else:
            print(f"No data found for the emoticon '{emoticon}'.")
    
    if pull_int is not None:
        user_choice = pull_int
    else:
        while(True):
            user_choice = int(input("Enter 1 to pull new posts from Slack, or 2 to just output details from the SQL database: "))
            if user_choice == int(1) or user_choice == int(2):
                break
            else:
                print ("Please select '1' or '2'. Try again...")
    if user_choice == int(1):
        count_emoticon_reactions(emoticon)

def main():
    global verbose
    global csv_flag
    global size_of_list
    global rate_limit_in_seconds
    
    global emoticon_string
    global pull_int
    global output_order
    
    parser = argparse.ArgumentParser(description="Slack Reaction Counter")
    
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
    parser.add_argument('-csv', '--csv', metavar='CSV_FILE', nargs='?', const=default_csv_name, help='Output user list to a CSV file')
    parser.add_argument('-count', '--count', type=int, metavar='COUNT_SIZE', help='Set size of output list')
    parser.add_argument('-r', '--rate', type=int, metavar='RATE_LIMIT', help='Set rate limit of calls per second')
    
    parser.add_argument('-e', '--reaction','--emoticon', type=str, metavar='EMOTICON_STR', help='Pass reaction emoticon')
    parser.add_argument('-p', '--pull', type=int, metavar='PULL_CHOICE', help='Pull from Slack & DB (1) or just from DB (2)')
    
    parser.add_argument('-o', '--output', type=str, metavar='OUTPUT_STR', help="set as 'desc' to change order")
    
    args = parser.parse_args()
    
    verbose = args.verbose
    
    if args.output is not None:
        if (args.output).lower() == "asc" or (args.output).lower() == "ascend":
            output_order = False
        if verbose:
            print("Output order: ", output_order)
      
    if args.count is not None:
        size_of_list = args.count
        if verbose:
            print("List size: ", size_of_list)
            
    if args.reaction is not None:
        emoticon_string = args.reaction
        if verbose:
            print("Reaction Emoticon: ", emoticon_string)
    
    if args.pull is not None:
        pull_int = args.pull
        if verbose:
            print("Pull selection: ", pull_int)
        
    if args.rate is not None:
        rate_limit_in_seconds = args.rate
        if verbose:
            print("Rate limit (seconds): ", rate_limit_in_seconds)

    if args.csv is not None:
        csv_flag = True
        csv_file = args.csv if args.csv != default_csv_name else None  # Use the provided filename or None if it's the default
        if verbose:
            print("CSV File: ",csv_file)
    else:
        csv_flag = False
        csv_file = None  # No CSV file name provided

    initialize_database()

    emoticon = get_emoticon_from_user()

    pull_data_option(emoticon)  # check with user if new data should be pulled
    user_reactions = get_user_reactions(emoticon)

    print_top_users(user_reactions, emoticon, csv_file=csv_file)

    
if __name__ == "__main__":
    main()
