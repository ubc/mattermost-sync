import base64
import re
import subprocess
import shlex
from urllib.error import HTTPError
import slack
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import time
from fastapi import requests
from flask import Flask, request, Response, jsonify
from slackeventsapi import SlackEventAdapter
import asyncio
import requests


load_dotenv()

app = Flask(__name__)

slack_event_adapter = SlackEventAdapter(os.environ.get('SLACK_SIGN_SECRET'),'/slack/events',app)

##OAuth Token
client = slack.WebClient(token=os.environ.get('SLACK_TOKEN'))

# Get the current date and time
current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

BOT_ID = client.api_call("auth.test")['user_id']

# Flag to control message processing
message_processed = False

# Track processed message timestamps to avoid duplicate posts
processed_messages = {}

# Time delay to prevent processing the same message more than once
MESSAGE_DELAY = 15  # Set the time in seconds


@slack_event_adapter.on('message')
def messageStartMessage(payload):
    event = payload.get('event', {})
    channel_id = event.get('channel')
    user_id = event.get('user')
    text = event.get('text')
    event_ts = event.get('ts')  # Slack message timestamp

    # Debounce: Check if the message has already been processed
    if event_ts in processed_messages:
        last_processed_time = processed_messages[event_ts]
        if time.time() - last_processed_time < MESSAGE_DELAY:
            print(f"Message {event_ts} already processed, skipping.")
            return  # Skip duplicate processing

    # Mark the message as processed
    processed_messages[event_ts] = time.time()

    # Only process messages not from the bot itself
    if BOT_ID != user_id:
        # Simulate OpenAI API call (you can replace this with actual OpenAI processing)
        # retPrompt = getOpenAI(text)  # Placeholder for OpenAI call


        # Send message to the Slack channel
        client.chat_postMessage(channel=channel_id, text="Message is being loaded...")

        # Send message with image using Block Kit
        client.chat_postMessage(
            channel=channel_id,
            text="*MM:* whatever..."
        )


@app.route('/whatever', methods=['POST'])
def messageWhatever():
    data = request.form

    channel_id = data.get('channel_id')
    user_id = data.get('user_id')

    text = data.get('text', '')

    # Only process messages not from the bot itself
    if BOT_ID != user_id:
        # Simulate OpenAI API call (you can replace this with actual OpenAI processing)
        retPrompt = text

        # Send message to the Slack channel
        client.chat_postMessage(channel=channel_id, text="Message is being loaded...")

        # Send message with image using Block Kit
        ret_result = {
            True: "Sync completed successfully",
            False: retPrompt
        }['200' in retPrompt]

        client.chat_postMessage(
            channel=channel_id,
            text="*MM:* " + ret_result
        )

        return Response(), 200


def run_sync_script(courses, verbosity="INFO"):
    # Fetch parameters from environment variables
    uid = os.environ.get('LDAP_UID')
    password = os.environ.get('LDAP_PASSWORD')
    ldap_url = os.environ.get('LDAP_URL')
    base = os.environ.get('LDAP_BASE')
    mattermost_url = os.environ.get('MATTERMOST_URL')
    token = os.environ.get('MATTERMOST_TOKEN')

    # Define the command to run sync.py with the arguments
    command = [
        "python", "./sync.py",
        "-u", uid,
        "-p", password,
        "-l", ldap_url,
        "-b", base,
        "-c", courses,  # This is passed directly into the function
        "-r", mattermost_url,
        "-t", token,
        "-v", verbosity  # Verbosity can still be passed, defaults to DEBUG
    ]

    try:
        # Run the sync.py script and wait for it to complete
        result = subprocess.run(command, check=True, text=True, capture_output=True)
        textout = result.stdout

        # Use regex to extract the line starting with 'reply:'
        match = re.search(r"reply: '.*?'", textout)

        if match:
            reply = match.group(0)  # Extract the matched 'reply' line
            textreply = reply
        else:
            textreply = "Sync complete. Please confirm the result in the Mattermost app."

        return textreply  # Return the output of the sync.py script
    except subprocess.CalledProcessError as e:
        return f"Error occurred while running sync script: {e}\n{e.stderr}"


@app.route('/sync', methods=['POST'])
def callSync():
    data = request.form

    channel_id = data.get('channel_id')
    user_id = data.get('user_id')

    # Extract the text field containing the additional parameters
    text = data.get('text', '')

    # Define the characters to remove
    special_chars = "=!@#%^&*)(][}{,:$?"

    # Remove all specified special characters
    text = ''.join(char for char in text if char not in special_chars)

    # Split the text into individual parts (assuming space-separated)
    params = text.split()

    # Extract individual parameters if they exist
    course_name = params[0] if len(params) > 0 else None
    course_number = params[1] if len(params) > 1 else None
    course_section = params[2] if len(params) > 2 else None
    course_academicYear = params[3] if len(params) > 3 else None
    course_role = params[4] if len(params) > 4 else "students"

    # Define a regex pattern to match years from 2022 to 2030
    year_pattern = r"(202[2-9]|2030)"
    course_year = re.search(year_pattern, params[3]).group(0) if len(params) > 3 and re.search(year_pattern,
                                                                                               params[3]) else "1970"
    # Only process messages not from the bot itself
    if BOT_ID != user_id:
        text = "Be precise and realistic as possible in your response to this message within two sentences. " + text

        str_course = course_name + " " + course_number + " " + course_section + " " + course_academicYear + course_role

        retPrompt = run_sync_script( str_course)

        retPrompt = retPrompt.replace(r"\r\n", "").replace("'", "")

        # Send message to the Slack channel
        client.chat_postMessage(channel=channel_id, text="Message is being loaded...")

        # Send message with image using Block Kit
        ret_result = {
            True: "Sync completed successfully",
            False: retPrompt
        }['200' in retPrompt]

        client.chat_postMessage(
            channel=channel_id,
            text="*MM:* " + ret_result
        )

        return Response(), 200



def get_teams_by_user_id(url, token, user_id, scheme='https', port=443):
    """
    Get all teams that a Mattermost user is a member of using their user_id.
    return: A list of teams the user is a member of, or an empty list if not found
    """
    api_url = f"{scheme}://{url}:{port}/api/v4/users/{user_id}/teams"
    headers = {'Authorization': f'Bearer {token}'}

    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()  # Raise an error for bad responses
        teams = response.json()

        return [{'team_id': team['id'], 'team_name': team['display_name']} for team in teams]

    except HTTPError as e:
        print(f'Failed to retrieve teams for user ID {user_id}: {e}')
        return []

def get_userid_by_username(url, token, username, scheme='https', port=443):
    """
    Get user ID by Mattermost username.
    return: User ID if found, None otherwise
    """
    api_url = f"{scheme}://{url}:{port}/api/v4/users/username/{username}"
    headers = {'Authorization': f'Bearer {token}'}

    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()  # Raise an error for bad responses
        user_data = response.json()
        return user_data.get('id')

    except HTTPError as e:
        print(f"Failed to retrieve user ID for username {username}: {e}")
        return None


def get_username_by_user_id(url, token, user_id, scheme='https', port=443):
    """
    Get the username of a Mattermost user using their user_id.
    return: The username of the user, or None if not found
    """
    api_url = f"{scheme}://{url}:{port}/api/v4/users/{user_id}"
    headers = {'Authorization': f'Bearer {token}'}

    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()  # Raise an error for bad responses
        user = response.json()

        return user.get('username')  # Return the username

    except HTTPError as e:
        print(f'Failed to retrieve username for user ID {user_id}: {e}')
        return None


def search_team_by_name(url, token, team_name, scheme='https', port=443):
    """
    Search for a team by its display name and return the team_id.
    return: team_id of the matching team or None if not found
    """
    api_url = f"{scheme}://{url}:{port}/api/v4/teams"
    headers = {'Authorization': f'Bearer {token}'}

    try:
        page = 0
        while True:
            response = requests.get(api_url, headers=headers, params={'page': page, 'per_page': 60})
            response.raise_for_status()  # Raise an error for bad responses
            teams = response.json()
            if not teams:
                break

            for team in teams:
                if team['display_name'].lower() == team_name.lower():
                    return team['id']

            page += 1

        return None

    except HTTPError as e:
        print(f'Failed to retrieve teams: {e}')
        return None

@app.route('/dumpteams', methods=['POST'])
def dump_teams():
    """
    Return the list of all teams from Mattermost via a POST request.
    The JSON request body must contain 'url', 'token', 'scheme', and 'port'.
    """

    url = os.environ.get('MATTERMOST_URL')
    token = os.environ.get('MATTERMOST_TOKEN')
    scheme = "https"  # Default scheme
    port = 443  # Default port

    api_url = f"{scheme}://{url}:{port}/api/v4/teams"
    headers = {'Authorization': f'Bearer {token}'}
    all_teams = []  # List to store all teams

    try:
        page = 0
        while True:
            response = requests.get(api_url, headers=headers, params={'page': page, 'per_page': 60})
            response.raise_for_status()  # Raise an error for bad responses
            teams = response.json()
            if not teams:
                break

            all_teams.extend([{'team_id': team['id'], 'team_name': team['display_name']} for team in teams if
                              team['delete_at'] == 0])

            page += 1

        return jsonify(all_teams), 200

    except HTTPError as e:
        return jsonify({'error': f'Failed to retrieve teams: {e}'}), 200

@app.route('/dumpusers', methods=['POST'])
def dump_active_users():
    """
    Return the list of all teams from Mattermost via a POST request.
    The JSON request body must contain 'url', 'token', 'scheme', and 'port'.
    """
    # Get parameters from the request body
    #data = request.get_json()
    # Set your parameters here
    url = os.environ.get('MATTERMOST_URL')
    token = os.environ.get('MATTERMOST_TOKEN')
    scheme = "https"  # Default scheme
    port = 443  # Default port


    api_url = f"{scheme}://{url}:{port}/api/v4/users"
    headers = {'Authorization': f'Bearer {token}'}
    all_users = []  # List to store all teams

    try:
        page = 0
        while True:
            response = requests.get(api_url, headers=headers, params={'page': page, 'per_page': 60})
            response.raise_for_status()  # Raise an error for bad responses
            users = response.json()
            if not users:
                break

            all_users.extend([user for user in users if user['delete_at'] != 0])

            page += 1

        # Return the team list as a JSON response
        return jsonify(all_users), 200

    except HTTPError as e:
        return jsonify({'error': f'Failed to retrieve teams: {e}'}), 200


@app.route('/get_team_members', methods=['POST'])
@app.route('/search_user', methods=['POST'])
def get_users_by_team():
    """
    Return the list of users (username and id) from a specific team in Mattermost.
    Expects a JSON payload with 'url', 'token', and 'team_id' keys.
    """
    data = request.form

    channel_id = data.get('channel_id')
    user_id = data.get('user_id')

    # Extract the text field containing the additional parameters
    text = data.get('text', '')

    # Split the text into individual parts (assuming space-separated)
    params = shlex.split(text)

    # Extract individual parameters if they exist
    parm1 = params[0] if len(params) > 0 else "None"
    parm2 = params[1] if len(params) > 1 else "None"
    parm3 = params[2] if len(params) > 2 else "None"
    parm4 = params[3] if len(params) > 3 else "None"


    url = os.environ.get('MATTERMOST_URL')
    token = os.environ.get('MATTERMOST_TOKEN')
    scheme = "https"  # Default scheme
    port = 443  # Default port

    team_name = str(parm1)
    team_id = search_team_by_name(url, token, team_name)

    if team_id:

        api_url = f"{scheme}://{url}:{port}/api/v4/teams/{team_id}/members"
        headers = {'Authorization': f'Bearer {token}'}
        team_users = []  # List to store users of the specific team

        try:
            response = requests.get(api_url, headers=headers)
            response.raise_for_status()  # Raise an error for bad responses
            users = response.json()

            team_users.extend([{'id': user['user_id'], 'name': get_username_by_user_id(url,token,user['user_id'])} for user in users])

            return jsonify(team_users)

        except HTTPError as e:
            return jsonify({'error': f'Failed to retrieve users for team {team_id}: {e}'}), 200

    else:
        return jsonify({'error': f'Failed to retrieve users for team {team_id}'}), 200


@app.route('/get_user_teams', methods=['POST'])
@app.route('/search_user_teams', methods=['POST'])
def get_teams_by_username():
    """
    Return the list of teams (team ID and team name) that a specific user is part of in Mattermost.
    Expects a JSON payload with 'url', 'token', and 'user_id' keys.
    """
    data = request.form

    channel_id = data.get('channel_id')
    user_id = data.get('user_id')

    text = data.get('text', '')

    params = shlex.split(text)

    parm1 = params[0] if len(params) > 0 else None

    url = os.environ.get('MATTERMOST_URL')
    token = os.environ.get('MATTERMOST_TOKEN')
    scheme = "https"
    port = 443

    user_id2 = get_userid_by_username(url, token, parm1)

    if parm1:
        user_id = get_userid_by_username(url, token, str(parm1))

    api_url = f"{scheme}://{url}:{port}/api/v4/users/{user_id}/teams"
    headers = {'Authorization': f'Bearer {token}'}

    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        teams = response.json()

        user_teams = [{'team_id': team['id'], 'team_name': team['display_name']} for team in teams]

        return jsonify(user_teams), 200  # Return the list of teams

    except HTTPError as e:
        return jsonify({'error': f'Failed to retrieve teams for user {user_id}: {e}'}), 200



#########################################

def add_user_to_team_in_mattermost(url, token, username, team_name, scheme='https', port=443):
    """
    Add a user to a team in Mattermost by username and team name.
    """

    # Get user ID by username
    user_id = get_userid_by_username(url, token, username)

    if not user_id:
        return {"error": f"User {username} not found"}, 200

    # Get team ID by team name
    team_id = get_teamid_by_name(url, token, team_name)
    if not team_id:
        return {"error": f"Team {team_name} not found"}, 200

    api_url = f"{scheme}://{url}:{port}/api/v4/teams/{team_id}/members"
    headers = {'Authorization': f'Bearer {token}'}
    payload = {
        "user_id": user_id,
        "team_id": team_id
    }

    try:
        response = requests.post(api_url, headers=headers, json=payload)
        response.raise_for_status()  # Raise an error for bad responses

        return {"message": f"User {username} added to team {team_name} successfully"}, 200  # Return success message

    except HTTPError as e:
        print(f"Failed to add user {username} to team {team_name}: {e}")
        return {"error": f"Failed to add user {username} to team {team_name}"}, 200


@app.route('/adduser_to_team', methods=['POST'])
@app.route('/adduser', methods=['POST'])
def add_user():
    """
    API route to add a user to a team in Mattermost.
    Expects a JSON payload with 'url', 'token', 'username', and 'teamname'.
    """


    data = request.form

    channel_id = data.get('channel_id')
    user_id = data.get('user_id')

    text = data.get('text', '')

    params = shlex.split(text)

    parm1 = params[0] if len(params) > 0 else "None"
    parm2 = params[1] if len(params) > 1 else "None"
    parm3 = params[2] if len(params) > 2 else "None"
    parm4 = params[3] if len(params) > 3 else "None"

    url = os.environ.get('MATTERMOST_URL')
    token = os.environ.get('MATTERMOST_TOKEN')
    scheme = "https"  # Default scheme
    port = 443  # Default port


    username = str(parm1)

    team_name = str(parm2)

    if not (url, token, username, team_name):
        return jsonify({"error": "Missing required parameters"}), 200

    result = add_user_to_team_in_mattermost(url, token, username, team_name)

    return jsonify(result[0]), result[1]  # Return the result and status code



def get_teamid_by_name(url, token, team_name, scheme='https', port=443):
    """
    Get the team ID by team name from Mattermost.
    """
    api_url = f"{scheme}://{url}:{port}/api/v4/teams"
    headers = {'Authorization': f'Bearer {token}'}


    api_url = f"{scheme}://{url}:{port}/api/v4/teams"
    headers = {'Authorization': f'Bearer {token}'}
    all_teams = []  # List to store all teams

    try:
        page = 0
        while True:
            response = requests.get(api_url, headers=headers, params={'page': page, 'per_page': 60})
            response.raise_for_status()  # Raise an error for bad responses
            teams = response.json()
            if not teams:
                break

            all_teams.extend([{'team_id': team['id'], 'team_name': team['display_name']} for team in teams if
                              team['delete_at'] == 0])

            page += 1


        for team in all_teams:
            if team['team_name'] == team_name:
                return team['team_id']

        return None

    except HTTPError as e:
        print(f"Failed to retrieve team ID for {team_name}: {e}")
        return None

#########################################

def activate_user_in_mattermost(url, token, username, scheme='https', port=443):
    """
    Activate a user in Mattermost by username.
    """

    user_id = get_userid_by_username(url, token, username)
    if not user_id:
        return {"error": f"User {username} not found"}, 200

    api_url = f"{scheme}://{url}:{port}/api/v4/users/{user_id}/active"
    headers = {'Authorization': f'Bearer {token}'}

    user_data = {
        'active': True
    }

    try:
        response = requests.put(api_url, headers=headers, json=user_data)
        response.raise_for_status()  # Raise an error for bad responses

        return {"message": f"User {username} activated successfully"}, 200  # Return success message

    except HTTPError as e:
        print(f"Failed to activate user {username}: {e}")
        return {"error": f"Failed to activate user {username}"}, 200


@app.route('/activateuser', methods=['POST'])
def activate_user():
    """
    API route to activate a user in Mattermost.
    Expects a JSON payload with 'url', 'token', and 'username'.
    """

    data = request.form

    channel_id = data.get('channel_id')
    user_id = data.get('user_id')

    text = data.get('text', '')

    params = shlex.split(text)

    parm1 = params[0] if len(params) > 0 else "None"
    parm2 = params[1] if len(params) > 1 else "None"
    parm3 = params[2] if len(params) > 2 else "None"
    parm4 = params[3] if len(params) > 3 else "None"


    url = os.environ.get('MATTERMOST_URL')
    token = os.environ.get('MATTERMOST_TOKEN')
    scheme = "https"  # Default scheme
    port = 443  # Default port


    username = str(parm1)

    if not (url, token, username):
        return jsonify({"error": "Missing required parameters"}), 200

    result = activate_user_in_mattermost(url, token, username)

    return jsonify(result[0]), result[1]



#########################################

def delete_user_in_mattermost(url, token, username, scheme='https', port=443):
    """
    Delete a user in Mattermost by username.
    """

    user_id = get_userid_by_username(url, token, username)
    if not user_id:
        return {"error": f"User {username} not found"}, 200

    api_url = f"{scheme}://{url}:{port}/api/v4/users/{user_id}"
    headers = {'Authorization': f'Bearer {token}'}

    try:
        # Make DELETE request to remove the user
        response = requests.delete(api_url, headers=headers)
        response.raise_for_status()  # Raise an error for bad responses

        return {"message": f"User {username} deleted successfully"}, 200  # Return success message

    except HTTPError as e:
        print(f"Failed to delete user {username}: {e}")
        return {"error": f"Failed to delete user {username}"}, 200


@app.route('/deleteuser', methods=['POST'])
@app.route('/deactivateuser', methods=['POST'])
def delete_user():
    """
    API route to delete a user in Mattermost.
    Expects a JSON payload with 'url', 'token', and 'username'.
    """

    data = request.form

    channel_id = data.get('channel_id')
    user_id = data.get('user_id')

    text = data.get('text', '')

    params = shlex.split(text)

    parm1 = params[0] if len(params) > 0 else "None"
    parm2 = params[1] if len(params) > 1 else "None"
    parm3 = params[2] if len(params) > 2 else "None"
    parm4 = params[3] if len(params) > 3 else "None"


    url = os.environ.get('MATTERMOST_URL')
    token = os.environ.get('MATTERMOST_TOKEN')
    scheme = "https"  # Default scheme
    port = 443  # Default port

    username = str(parm1)

    if not (url, token, username):
        return jsonify({"error": "Missing required parameters"}), 200

    result = delete_user_in_mattermost(url, token, username)

    return jsonify(result[0]), result[1]  # Return the result and status code


#########################################

def create_user_in_mattermost(url, token, username, useremail, userpassword, scheme='https', port=443):
    """
    Create a new user in Mattermost with the given username, email, and password.
    """
    api_url = f"{scheme}://{url}:{port}/api/v4/users"
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

    user_data = {
        "email": useremail,
        "username": username,
        "password": userpassword,
        'allow_see_email': True
    }

    try:
        response = requests.post(api_url, headers=headers, json=user_data)
        response.raise_for_status()

        return response.json()

    except HTTPError as e:
        print(f"Failed to create user {username}: {e}")
        return None


@app.route('/createuser', methods=['POST'])
def create_user():
    """
    API route to create a new user in Mattermost.
    Expects a JSON payload with 'url', 'token', 'username', 'useremail', and 'userpassword'.
    """


    data = request.form

    channel_id = data.get('channel_id')
    user_id = data.get('user_id')

    text = data.get('text', '')

    params = shlex.split(text)

    parm1 = params[0] if len(params) > 0 else "None"
    parm2 = params[1] if len(params) > 1 else "None"
    parm3 = params[2] if len(params) > 2 else "None"
    parm4 = params[3] if len(params) > 3 else "None"


    url = os.environ.get('MATTERMOST_URL')
    token = os.environ.get('MATTERMOST_TOKEN')
    scheme = "https"  # Default scheme
    port = 443  # Default port

    username = parm1
    useremail = parm2
    base64_userpassword = parm3

    if not (url, token, username, useremail, base64_userpassword):
        return jsonify({"error": "Missing required parameters"}), 200

    # Decode Base64 password
    try:
        userpassword = base64.b64decode(base64_userpassword).decode('utf-8')
    except Exception as e:
        return jsonify({'error': f'Failed to decode Base64 password: {e}'}), 200


    user_info = create_user_in_mattermost(url, token, username, useremail, userpassword)

    if user_info:
        return jsonify(user_info), 200
    else:
        return jsonify({"error": f"Failed to create user {username}"}), 200


#########################################

def get_userinfo_by_username(url, token, username, scheme='https', port=443):
    """
    Retrieve user information from Mattermost by username.
    """
    api_url = f"{scheme}://{url}:{port}/api/v4/users/username/{username}"
    headers = {'Authorization': f'Bearer {token}'}

    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        user_data = response.json()
        return user_data
    except HTTPError as e:
        print(f"Failed to retrieve user information for username {username}: {e}")
        return None


@app.route('/userinfo', methods=['POST'])
def get_user_info():
    """
    API route to retrieve user info by username.
    Expects a JSON payload with 'url', 'token', and 'username'.
    """

    data = request.form

    channel_id = data.get('channel_id')
    user_id = data.get('user_id')

    text = data.get('text', '')

    params = shlex.split(text)

    parm1 = params[0] if len(params) > 0 else "None"
    parm2 = params[1] if len(params) > 1 else "None"
    parm3 = params[2] if len(params) > 2 else "None"
    parm4 = params[3] if len(params) > 3 else "None"


    url = os.environ.get('MATTERMOST_URL')
    token = os.environ.get('MATTERMOST_TOKEN')
    scheme = "https"  # Default scheme
    port = 443  # Default port

    username = str(parm1)

    if not (url and token and username):
        return jsonify({"error": "Missing required parameters"}), 200

    user_info = get_userinfo_by_username(url, token, username)

    if user_info:
        return jsonify(user_info), 200
    else:
        return jsonify({"error": f"User {username} not found"}), 200

#########################################


def change_user_password(url, token, user_id, new_password, scheme='https', port=443):
    """
    Change the user's password in Mattermost.
    """
    api_url = f"{scheme}://{url}:{port}/api/v4/users/{user_id}/password"
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

    # Mattermost requires old_password for security, use a dummy value here if not available
    payload = {
        "new_password": new_password,
        "current_password": "dummy_current_password"
    }

    try:
        response = requests.put(api_url, headers=headers, json=payload)
        response.raise_for_status()
        return True  # Password change successful
    except HTTPError as e:
        print(f"Failed to change password for user {user_id}: {e}")
        return False


@app.route('/change_pwd', methods=['POST'])
def change_pwd():
    """
    API route to change the password of a Mattermost user.
    Expects JSON payload with 'url', 'token', 'username', and 'newpassword'.
    """

    data = request.form

    channel_id = data.get('channel_id')
    user_id = data.get('user_id')

    text = data.get('text', '')

    params = shlex.split(text)

    parm1 = params[0] if len(params) > 0 else "None"
    parm2 = params[1] if len(params) > 1 else "None"
    parm3 = params[2] if len(params) > 2 else "None"
    parm4 = params[3] if len(params) > 3 else "None"


    url = os.environ.get('MATTERMOST_URL')
    token = os.environ.get('MATTERMOST_TOKEN')
    scheme = "https"  # Default scheme
    port = 443  # Default port

    username = str(parm1)

    base64_new_password = str(parm2)
    base64_pass_user_id = str(parm3)

    if not (url and token and username and base64_new_password and base64_pass_user_id):
        return jsonify({"error": "Missing required parameters"}), 400

    try:
        new_password = base64.b64decode(base64_new_password).decode('utf-8')
        pass_user_id = base64.b64decode(base64_pass_user_id).decode('utf-8')
    except Exception as e:
        return jsonify({'error': f'Failed to decode Base64 parameters: {e}'}), 400


    user_id = get_userid_by_username(url, token, username)
    if not user_id:
        return jsonify({'error': f'User {username} not found'}), 404

    if pass_user_id != user_id:
        return jsonify({'error': 'Passed user_id does not match the actual user_id for the username'}), 403

    if user_id:
        success = change_user_password(url, token, user_id, new_password)
        if success:
            return jsonify({"message": f"Password changed for user {username}"}), 200
        else:
            return jsonify({"error": "Failed to change password"}), 500
    else:
        return jsonify({"error": f"User {username} not found"}), 404


#########################################

@app.route('/change_userinfo', methods=['POST'])
def change_userinfo():
    """
    API route to change a user's email, first name, and/or last name in Mattermost.
    Expects a form with 'url', 'token', and Base64-encoded 'user_id' as well as optional 'email', 'firstname', and 'lastname'.
    """

    data = request.form

    channel_id = data.get('channel_id')
    user_id = data.get('user_id')

    text = data.get('text', '')

    params = shlex.split(text)

    # Extract individual parameters
    parm1 = params[0] if len(params) > 0 else "None"  # Base64-encoded user_id
    parm2 = params[1] if len(params) > 1 else None  # new_email (optional)
    parm3 = params[2] if len(params) > 2 else None  # new_firstname (optional)
    parm4 = params[3] if len(params) > 3 else None  # new_lastname (optional)
    parm5 = params[4] if len(params) > 4 else None  # new_nickname (optional)
    parm6 = params[5] if len(params) > 5 else None  # new_roles (optional)

    url = os.environ.get('MATTERMOST_URL')
    token = os.environ.get('MATTERMOST_TOKEN')
    scheme = "https"
    port = 443

    try:
        decoded_user_id = base64.b64decode(parm1).decode('utf-8')

        api_url = f"{scheme}://{url}:{port}/api/v4/users/{decoded_user_id}"
        headers = {'Authorization': f'Bearer {token}'}

        user_response = requests.get(api_url, headers=headers)
        user_response.raise_for_status()
        user_info = user_response.json()

        if user_info['id'] != decoded_user_id:
            return jsonify({'error': 'User ID verification failed. Please check the encoded user ID.'}), 400

        update_data = {}
        if parm2:  # Update email if provided
            update_data['email'] = parm2
        if parm3:  # Update first name if provided
            update_data['first_name'] = parm3
        if parm4:  # Update last name if provided
            update_data['last_name'] = parm4
        if parm5:  # Update nickname if provided
            update_data['nickname'] = parm5

        # Define valid Mattermost roles
        roles = str(parm6)
        valid_roles = ["system_user", "system_admin", "team_admin", "channel_admin"]

        # Validate roles if provided
        if roles:
            role_list = [role.strip() for role in roles.split(',')]  # Split roles and strip whitespace
            invalid_roles = [role for role in role_list if role not in valid_roles]

            if invalid_roles:
                return jsonify({'error': 'Invalid roles specified: {}. Must be one of: {}'.format(
                    invalid_roles, valid_roles)}), 200
            else:

                roles_str = " ".join(role_list)

                roles_url = f"{scheme}://{url}:{port}/api/v4/users/{decoded_user_id}/roles"
                roles_payload = {'roles': roles_str}
                roles_response = requests.put(roles_url, headers=headers, json=roles_payload)
                roles_response.raise_for_status()

        if not update_data:
            return jsonify({'error': 'No new information provided to update.'}), 200

        update_url = f"{scheme}://{url}:{port}/api/v4/users/{decoded_user_id}/patch"
        update_response = requests.put(update_url, headers=headers, json=update_data)
        update_response.raise_for_status()

        return jsonify({'success': 'User information updated successfully.'}), 200

    except requests.exceptions.HTTPError as e:
        return jsonify({'error': f'Failed to update user information: {str(e)}'}), 200
    except base64.binascii.Error:
        return jsonify({'error': 'Invalid Base64-encoded user ID.'}), 200


#########################################

@app.route('/remove_user_from_team', methods=['POST'])
def remove_user_from_team():
    """
    API route to remove a user from a team in Mattermost.
    Expects a form with 'url', 'token', 'username', and 'teamname'.
    """


    # Retrieve the form data
    data = request.form

    # Extract the channel_id, user_id, and text from the form
    channel_id = data.get('channel_id')
    user_id = data.get('user_id')
    text = data.get('text', '')

    # Parse the input parameters from the text
    params = shlex.split(text)
    parm1 = params[0] if len(params) > 0 else None  # username
    parm2 = params[1] if len(params) > 1 else None  # teamname

    # Set the Mattermost URL and token from environment variables
    url = os.environ.get('MATTERMOST_URL')
    token = os.environ.get('MATTERMOST_TOKEN')
    scheme = "https"  # Default scheme
    port = 443  # Default port

    # If required parameters are missing, return an error
    if not (url and token and parm1 and parm2):
        return jsonify({"error": "Missing required parameters"}), 200

    # Extract the username and teamname from parameters
    username = str(parm1)
    team_name = str(parm2)

    # Get the user ID based on the username
    user_id = get_userid_by_username(url, token, username)
    if not user_id:
        return jsonify({'error': f"User {username} not found"}), 200

    # Get the team ID based on the team name
    team_id = get_teamid_by_name(url, token, team_name)
    if not team_id:
        return jsonify({'error': f"Team {team_name} not found"}), 200

    # Construct the API URL to remove the user from the team
    api_url = f"{scheme}://{url}:{port}/api/v4/teams/{team_id}/members/{user_id}"
    headers = {'Authorization': f'Bearer {token}'}

    try:
        # Make the DELETE request to remove the user from the team
        response = requests.delete(api_url, headers=headers)
        response.raise_for_status()

        # Return success message if no exceptions were raised
        return jsonify({"message": f"User {username} removed from team {team_name} successfully"}), 200

    except requests.HTTPError as e:
        print(f"Failed to remove user {username} from team {team_name}: {e}")
        return jsonify({'error': f"Failed to remove user {username} from team {team_name}: {e}"}), 200

#########################################

@app.route('/whatever', methods=['POST'])
def whatever():
    data = request.form

    channel_id = data.get('channel_id')
    user_id = data.get('user_id')

    text = data.get('text', '')

    params = shlex.split(text)

    parm1 = params[0] if len(params) > 0 else "None"
    parm2 = params[1] if len(params) > 1 else "None"
    parm3 = params[2] if len(params) > 2 else "None"
    parm4 = params[3] if len(params) > 3 else "None"


    if BOT_ID != user_id:

        str_course = parm1 + " " + parm2 + " " + parm3 + " " + parm4

        retPrompt = str_course
        retPrompt = retPrompt.replace(r"\r\n", "").replace("'", "")

        client.chat_postMessage(channel=channel_id, text="Message is being loaded...")

        ret_result = {
            True: "Sync completed successfully",
            False: retPrompt
        }['200' in retPrompt]

        client.chat_postMessage(
            channel=channel_id,
            text="*MM:* " + ret_result
        )

        return Response(), 200



if __name__ == "__main__":
    app.run(host='0.0.0.0', port=443)



