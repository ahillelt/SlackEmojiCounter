import os
import time
import sqlite3
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from collections import defaultdict
from datetime import datetime

# params
client = WebClient(token='INSERT_YOUR_SLACK_APP_TOKEN') #ideally pull securely
size_of_list = 25
rate_limit_in_seconds = 2
database = 'slack_reactions.db'

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

# Database setup
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
    print("Database initialized and reactions table created.")

def insert_reaction(message_id, user_id, reaction, count, date):
    conn = sqlite3.connect(database)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO reactions (message_id, user_id, reaction, count, date)
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
        print(f"Error fetching user info for {user_id}: {e.response['error']}")
        return None

def get_user_names(user_ids):
    user_names = {}
    for user_id in user_ids:
        try:
            response = client.users_info(user=user_id)
            user_names[user_id] = response['user']['real_name']
        except SlackApiError as e:
            print(f"Error fetching user info for {user_id}: {e.response['error']}")
            user_names[user_id] = "Unknown User"
    return user_names

def get_channels():
    try:
        response = client.conversations_list()
        channels = response['channels']
        return [(channel['id'], channel['name']) for channel in channels]
    except SlackApiError as e:
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
        print(f"Error fetching messages in thread {thread_ts} from channel {channel_id}: {e.response['error']}")
        return []

def get_channel_members(channel_id):
    try:
        response = client.conversations_members(channel=channel_id)
        return response['members']
    except SlackApiError as e:
        print(f"Error fetching members for channel {channel_id}: {e.response['error']}")
        return []

#### Count Functions

def count_emoticon_reactions(emoticon):
    channels = get_channels()
    user_reactions = defaultdict(int)

    for channel_id, channel_name in channels:
        users = get_channel_members(channel_id)
        messages = get_all_messages(channel_id, channel_name)
        for message in messages:
            message_date = datetime.fromtimestamp(float(message['ts'])).strftime('%Y-%m-%d')
            if 'reactions' in message:
                for reaction in message['reactions']:
                    if reaction['name'] == emoticon:
                        if not check_reaction_exists(message['ts'], message['user'], reaction['name']):
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
                                if not check_reaction_exists(thread_message['ts'], thread_message['user'], reaction['name']):
                                    print(f"Inserting thread reaction: {thread_message['ts']}, {thread_message['user']}, {reaction['name']}, {reaction['count']}, {thread_message_date}")
                                    insert_reaction(thread_message['ts'], thread_message['user'], reaction['name'], reaction['count'], thread_message_date)
                                    user_reactions[thread_message['user']] += reaction['count']

    return user_reactions
    
def print_database(database):
    # Display contents of the database for verification
    conn = sqlite3.connect(database)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM reactions')
    rows = cursor.fetchall()
    print("Database contents:")
    for row in rows:
        print(row)
    conn.close()
    
def print_top_users(user_reactions, emoticon):
    sorted_reactions = sorted(user_reactions, key=lambda x: x[1], reverse=True)
    top_users = sorted_reactions[:size_of_list]

    user_ids = [user for user, count in top_users]
    user_names = get_user_names(user_ids)

    print(f"Top users who received '{emoticon}' reactions:")
    for user, count in top_users:
        print(f"{user_names[user]}: {count} reactions")

def get_emoticon_from_user():
    emoticon = input("Enter the emoticon to scan for (without colons, e.g., '+1'): ")
    return emoticon

def main():
    initialize_database()
    
    emoticon = get_emoticon_from_user()
    
    count_emoticon_reactions(emoticon) # Remember we have a SQLite database now
    
    user_reactions = get_user_reactions(emoticon)

    print_database(database)
    print_top_users(user_reactions, emoticon)
    
    

if __name__ == "__main__":
    main()
