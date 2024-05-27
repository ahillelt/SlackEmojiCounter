import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from collections import defaultdict

client = WebClient(token='ENTER_YOUR_SLACK_APP_TOKEN')
size_of_list = 10

def get_channels():
    try:
        response = client.conversations_list()
        channels = response['channels']
        return [(channel['id'], channel['name']) for channel in channels]
    except SlackApiError as e:
        print(f"Error fetching channels: {e.response['error']}")
        return []

def get_messages(channel_id, channel_name):
    try:
        # Check if bot is a member of the channel
        response = client.conversations_info(channel=channel_id)
        if not response['channel']['is_member']:
            print(f"Bot is not a member of channel {channel_name} (ID: {channel_id}), skipping.")
            return []
        
        # Fetch messages
        response = client.conversations_history(channel=channel_id)
        messages = response['messages']
        return messages
    except SlackApiError as e:
        print(f"Error fetching messages from channel {channel_name} (ID: {channel_id}): {e.response['error']}")
        return []

def count_emoticon_reactions(emoticon):
    channels = get_channels()
    user_reactions = defaultdict(int)
    
    for channel_id, channel_name in channels:
        messages = get_messages(channel_id, channel_name)
        for message in messages:
            if 'reactions' in message:
                for reaction in message['reactions']:
                    if reaction['name'] == emoticon:
                        for user in reaction['users']:
                            user_reactions[user] += 1
    return user_reactions

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

def main():
    emoticon = input("Enter the emoticon to scan for (without colons, e.g., 'thumbsup'): ")
    user_reactions = count_emoticon_reactions(emoticon)
    
    sorted_reactions = sorted(user_reactions.items(), key=lambda x: x[1], reverse=True)
    top_users = sorted_reactions[:size_of_list]  # pull size_of_list number of people
    
    user_ids = [user for user, count in top_users]
    user_names = get_user_names(user_ids)
    
    print(f"Top users with '{emoticon}' reactions:")
    for user, count in top_users:
        print(f"{user_names[user]}: {count} reactions")

if __name__ == "__main__":
    main()
