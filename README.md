Written by: Alon Hillel-Tuch

This Python script scans a Slack workspace to count the number of reactions for a specific emoticon and tallies the top users who used that emoticon. It utilizes the Slack API to fetch messages and reactions from channels the bot is a member of.

## Features
* Scans all channels for specific emoticon reaction.
* Counts the number of times each user received the specified emoticon as a reaction to their post(s).
* Allows you to collect select data and store locally, can be beneficial for Slack accounts with limited history retention
* Outputs the top users with the most reactions for the specified emoticon.
* Provides basic error messages if the bot is not a member of certain channels, including channel names and IDs. Use this to invite or not.
* Sanitized SQL database, doesn't need encryption for confidentiality purposes (integrity and non-repudiation not considered)
* Command line argument support
  

## Prerequisites
* Python 3.x
* slack_sdk library (pip install slack_sdk)
* A Slack app with a bot token and necessary permissions (channels:history, groups:history, im:history, mpim:history, reactions:read, users:read).

## Setup
* Create a Slack app and obtain a bot token with the required scopes.
* (NO LONGER NEEDED) Invite the bot to the channels you want it to scan.
* Replace 'your-slack-bot-token' in the script with your actual bot token.
* Feel free to tweak the rate-limiter for your specific Slack configuration. Set to not trigger the basic (free) Slack workspace params.

## Usage
1. Run the script:
```
python SlackCounter.py
```

If the SQL database does not exist locally yet, it will be created at this point. 

2. Enter the emoticon name (without colons, e.g., +1, rocket, heart) when prompted.
3. The script will output the top users (received the most of the specified emoticon), along with a tally of the number of reactions received.

### Command Line

The script supports command line arguments:

```
options:
  -h, --help            show this help message and exit
  -v, --verbose         Enable verbose output
  -csv [CSV_FILE], --csv [CSV_FILE]
                        Output user list to a CSV file
  -count COUNT_SIZE, --count COUNT_SIZE
                        Set size of output list
  -r RATE_LIMIT, --rate RATE_LIMIT
                        Set rate limit of calls per second
  -e EMOTICON_STR, --reaction EMOTICON_STR, --emoticon EMOTICON_STR
                        Pass reaction emoticon
  -p PULL_CHOICE, --pull PULL_CHOICE
                        Pull from Slack & DB (1) or just from DB (2)
  -o OUTPUT_STR, --output OUTPUT_STR
                        set as 'asc' to change order
```
#### -csv [CSV_FILE]
You can call 'verbose mode' to get a more detailed output of work done. Only required for diagnosing or curious parties. You can pass a filename or leave blank, in which case it defualts to 'SlackCounter.csv'.

```
python SlackCounter.py -V output.csv
```
#### -count COUNT_SIZE
Allows you to define the size of the list you are pulling, for example '-count 5' would output a list of size 5

```
python SlackCounter.py -count 5
```

#### -r RATE_LIMIT

Example, 10 second wait per request rate limit
```
python SlackCounter.py -r 10
```

#### -e [EMOTICON_STR]
Allows you to pass the reation emoticon name instead of via interface

```
python SlackCounter.py -e nyu
```

#### -p PULL_CHOICE
Allows to to pass your selection of pulling from Slack and the DB (1) or just from the DB (2)  instead of via interface

```
python SlackCounter.py -p 1
```

#### -o OUTPUT_CHOICE
Allows you to set the output in ascending versus descending order. Options "asc" or "ascend":

```
python SlackCounter.py -o ascend
```

All arguments can be combined. For example verbose mode enabled, custom csv, 5 second rate limit, list size of 20, pull option 1, emoticon 'nyu', and output ascending:
```
python SlackCounter.py -v -r 5 -csv output.csv -e nyu -p 1 -o asc
```
