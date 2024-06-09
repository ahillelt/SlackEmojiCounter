Written by: Alon Hillel-Tuch

This Python script scans a Slack workspace to count the number of reactions for a specific emoticon and tallies the top users who used that emoticon. It utilizes the Slack API to fetch messages and reactions from channels the bot is a member of.

## Features
* Scans all channels for specific emoticon reaction.
* Counts the number of times each user received the specified emoticon as a reaction to their post(s).
* Outputs the top users with the most reactions for the specified emoticon.
* Provides basic error messages if the bot is not a member of certain channels, including channel names and IDs. Use this to invite or not.
* Sanitized SQL database, doesn't need encryption for confidentiality purposes (integrity and non-repudiation not considered)

## Prerequisites
* Python 3.x
* slack_sdk library (pip install slack_sdk)
* A Slack app with a bot token and necessary permissions (channels:history, groups:history, im:history, mpim:history, reactions:read, users:read).

## Setup
* Create a Slack app and obtain a bot token with the required scopes.
* Invite the bot to the channels you want it to scan.
* Replace 'your-slack-bot-token' in the script with your actual bot token.
* Feel free to tweak the rate-limiter for your specific Slack configuration. Set to not trigger the basic (free) Slack workspace params.

## Usage
1. Run the script:
```
python counter.py
```
2. Enter the emoticon name (without colons, e.g., +1, rocket, heart) when prompted.
3. The script will output the top users (received the most of the specified emoticon), along with a tally of the number of reactions received.
