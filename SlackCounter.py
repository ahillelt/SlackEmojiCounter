# Written by: Alon Hillel-Tuch

import os
import time
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from collections import defaultdict

# params
client = WebClient(token='ENTER_YOUR_SLACK_APP_TOKEN')
size_of_list = 25
rate_limit_in_seconds = 2

# Global variable to track the last time a request was made (rate limiting)
last_request_time = None

#### Slack API Helper Funcs

def rate_limit():
    global last_request_time
    if last_request_time is not None:
        # Calculate the time elapsed since the last request
        elapsed_time = time.time() - last_request_time
        # If less than a second has passed, sleep to ensure we wait at least a second
        if elapsed_time < rate_limit_in_seconds:
            time.sleep(rate_limit_in_seconds - elapsed_time)
    # Update the last request time
    last_request_time = time.time()

#### Information Gathering

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
        # Rate limit the request
        rate_limit()

        # Fetch all messages, including replies and threads
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
        # Rate limit the request
        rate_limit()

        # Fetch all messages in the thread
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
        # Fetch all users in the channel
        users = get_channel_members(channel_id)

        # Fetch all messages in the channel
        messages = get_all_messages(channel_id, channel_name)
        for message in messages:
            # Check if the message has reactions
            if 'reactions' in message:
                for reaction in message['reactions']:
                    # Check if the specified emoticon is among the reactions
                    if reaction['name'] == emoticon:
                        # Increment the reaction count for the author of the message
                        user_reactions[message['user']] += reaction['count']

            # Check for reactions on replies within threads
            if 'thread_ts' in message:
                thread_messages = get_thread_messages(channel_id, message['thread_ts'])
                for thread_message in thread_messages:
                    if 'reactions' in thread_message:
                        for reaction in thread_message['reactions']:
                            # Check if the specified emoticon is among the reactions
                            if reaction['name'] == emoticon:
                                # Increment the reaction count for the author of the thread message
                                user_reactions[thread_message['user']] += reaction['count']

                            # Also, count reactions on subsequent messages within the thread
                            for reply_reaction in thread_message['reactions']:
                                if 'user' in reply_reaction:
                                    if reply_reaction['name'] == emoticon:
                                        user_reactions[reply_reaction['user']] += reply_reaction['count']

    return user_reactions

def main():
    emoticon = input("Enter the emoticon to scan for (without colons, e.g., '+1'): ")
    user_reactions = count_emoticon_reactions(emoticon)

    sorted_reactions = sorted(user_reactions.items(), key=lambda x: x[1], reverse=True)
    top_users = sorted_reactions[:size_of_list]  # pull size_of_list number of people

    user_ids = [user for user, count in top_users]
    user_names = get_user_names(user_ids)

    print(f"Top users who received '{emoticon}' reactions:")
    for user, count in top_users:
        print(f"{user_names[user]}: {count} reactions")

if __name__ == "__main__":
    main()
