import os
import json
import requests
from datetime import datetime

def get_github_activity():
    # Get recent activity using GitHub API
    headers = {
        'Authorization': f'token {os.getenv("GITHUB_TOKEN")}',
        'Accept': 'application/vnd.github+json'
    }
    
    # Get recent events
    events_url = 'https://api.github.com/users/virajverse/events'
    response = requests.get(events_url, headers=headers)
    events = response.json()
    
    # Process events
    activity = []
    for event in events[:5]:  # Get last 5 events
        event_type = event.get('type', '')
        repo_name = event.get('repo', {}).get('name', '')
        created_at = event.get('created_at', '')
        
        if event_type and repo_name and created_at:
            activity.append({
                'type': event_type,
                'repo': repo_name,
                'time': created_at
            })
    
    return activity

def update_readme(activity_data):
    # Read current README
    with open('PROFILE-README.md', 'r', encoding='utf-8') as f:
        readme = f.read()
    
    # Generate activity section
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    activity_section = f"""## 🕒 Real-Time Activity

_Last updated: {now}_

### Recent GitHub Activity\n"""
    
    if activity_data:
        for activity in activity_data:
            event_type = activity['type'].replace('Event', '').replace('Push', 'Pushed to')
            activity_section += f"- **{event_type}** on `{activity['repo']}` at {activity['time']}\n"
    else:
        activity_section += "No recent activity to display. Check back soon!\n"
    
    # Update README
    if '## 🕒 Real-Time Activity' in readme:
        # Update existing section
        start = readme.find('## 🕒 Real-Time Activity')
        end = readme.find('## ', start + 1)
        if end == -1:  # If it's the last section
            readme = readme[:start] + activity_section
        else:
            readme = readme[:start] + activity_section + readme[end:]
    else:
        # Add new section after the introduction
        intro_end = readme.find('## ', 1)  # Find start of next section
        readme = readme[:intro_end] + '\n' + activity_section + '\n' + readme[intro_end:]
    
    # Write back to README
    with open('PROFILE-README.md', 'w', encoding='utf-8') as f:
        f.write(readme)

if __name__ == "__main__":
    activity = get_github_activity()
    update_readme(activity)
