import os
import sys
import json
import requests
from datetime import datetime

# Reconfigure stdout/stderr to UTF-8 to prevent encoding crashes in certain shells/OSes
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass
if sys.stderr.encoding != 'utf-8':
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

def get_recent_activity():
    # Fetch recent events from GitHub API
    headers = {
        'Accept': 'application/vnd.github+json'
    }
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token:
        headers['Authorization'] = f'token {github_token}'
        
    events_url = 'https://api.github.com/users/virajverse/events'
    try:
        response = requests.get(events_url, headers=headers)
        if response.status_code != 200:
            print(f"Error fetching GitHub events: {response.status_code}")
            return []
        return response.json()
    except Exception as e:
        print(f"Exception fetching events: {e}")
        return []

def parse_activities(events):
    parsed = []
    # Loop through events from last 24 hours
    for event in events[:15]:
        event_type = event.get('type', '')
        repo_name = event.get('repo', {}).get('name', '')
        created_at = event.get('created_at', '')
        
        # Only extract relevant developer actions
        if event_type == 'PushEvent':
            commits = event.get('payload', {}).get('commits', [])
            commit_msgs = [c.get('message', '') for c in commits]
            parsed.append({
                'type': 'Push',
                'repo': repo_name,
                'time': created_at,
                'details': f"Pushed to {repo_name} with messages: " + ", ".join([f"'{m}'" for m in commit_msgs])
            })
        elif event_type == 'IssuesEvent':
            action = event.get('payload', {}).get('action', '')
            issue_title = event.get('payload', {}).get('issue', {}).get('title', '')
            parsed.append({
                'type': 'Issue',
                'repo': repo_name,
                'time': created_at,
                'details': f"{action.capitalize()} issue '{issue_title}' on {repo_name}"
            })
        elif event_type == 'PullRequestEvent':
            action = event.get('payload', {}).get('action', '')
            pr_title = event.get('payload', {}).get('pull_request', {}).get('title', '')
            parsed.append({
                'type': 'Pull Request',
                'repo': repo_name,
                'time': created_at,
                'details': f"{action.capitalize()} PR '{pr_title}' on {repo_name}"
            })
        elif event_type == 'CreateEvent':
            ref_type = event.get('payload', {}).get('ref_type', '')
            parsed.append({
                'type': 'Create',
                'repo': repo_name,
                'time': created_at,
                'details': f"Created a new {ref_type} on {repo_name}"
            })
    return parsed

def generate_story(activities):
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        print("GEMINI_API_KEY not found in environment. Falling back to simple log list.")
        return None

    if not activities:
        # Default prompt when there's no commit activity
        prompt = (
            "Write a short, engaging, and professional developer status update stating that I (Viraj) am currently "
            "refining my codebase, planning new features, or researching advanced technologies like Rust and Web3. "
            "Keep it to exactly 1 sentence, write it in first-person ('I...'), and include an emoji. "
            "Do not include any quote marks or surrounding text."
        )
    else:
        activities_text = "\n".join([f"- {a['details']}" for a in activities])
        prompt = f"""
You are the personal portfolio AI agent for Viraj Srivastava (GitHub: virajverse).
Below is a list of recent Git activities and commit messages performed by Viraj in the last 6 hours:
{activities_text}

Based on this activity, write a premium, short, and highly engaging "Developer Diary" entry in the FIRST PERSON ("I worked on...", "I built...", "I solved...").
Guidelines:
- Keep it under 2 sentences.
- Make it sound energetic, professional, and highlight the technical achievements (e.g. optimizing speed, adding authentication, fixing bugs).
- Use 1 or 2 relevant emojis.
- Do NOT use markdown code blocks or wrapper text. Just output the plain text diary entry.
- Do NOT make things up; stick strictly to the actual code changes shown in the commits.
"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }]
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            result = response.json()
            story = result['candidates'][0]['content']['parts'][0]['text'].strip()
            return story
        else:
            print(f"Gemini API returned status code {response.status_code}: {response.text}")
            return None
    except Exception as e:
        print(f"Exception calling Gemini API: {e}")
        return None

def update_history_file(new_story):
    today_str = datetime.utcnow().strftime('%Y-%m-%d')
    history_file = 'history.json'
    
    # Read existing history
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except Exception:
            history = []
    else:
        history = []
        
    # Check if we already have an entry for today with the same story to avoid duplicate runs
    duplicate = False
    for entry in history:
        if entry.get('date') == today_str and entry.get('story') == new_story:
            duplicate = True
            break
            
    if not duplicate:
        # Insert at the beginning of the list
        history.insert(0, {
            'date': today_str,
            'story': new_story
        })
        # Keep maximum of 50 logs in history.json to avoid bloating
        history = history[:50]
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
            
    return history

def update_readme_files(story, history_list):
    readme_file = 'README.md'
    if not os.path.exists(readme_file):
        print("README.md not found.")
        return
        
    with open(readme_file, 'r', encoding='utf-8') as f:
        readme = f.read()

    # 1. Update AI Diary Section
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    diary_content = f"\n\n> 🤖 **AI Dev Diary** (Updated {now}):\n> *\"{story}\"*\n\n"
    
    start_tag = '<!-- START_SECTION:ai-diary -->'
    end_tag = '<!-- END_SECTION:ai-diary -->'
    
    if start_tag in readme and end_tag in readme:
        start_idx = readme.find(start_tag) + len(start_tag)
        end_idx = readme.find(end_tag)
        readme = readme[:start_idx] + diary_content + readme[end_idx:]
    else:
        print("AI Diary comment tags not found in README.md.")

    # 2. Update Archive Section
    archive_html = "\n\n<details>\n  <summary>📂 View Dev Diary History (Past Stories)</summary>\n  <ul>\n"
    # Skip the first one if it's the currently displayed story
    for entry in history_list[1:10]:  # Show past 9 entries in archive
        archive_html += f"    <li><strong>{entry['date']}:</strong> {entry['story']}</li>\n"
    archive_html += "  </ul>\n</details>\n\n"
    
    archive_start = '<!-- START_SECTION:ai-diary-archive -->'
    archive_end = '<!-- END_SECTION:ai-diary-archive -->'
    
    if archive_start in readme and archive_end in readme:
        start_idx = readme.find(archive_start) + len(archive_start)
        end_idx = readme.find(archive_end)
        readme = readme[:start_idx] + archive_html + readme[end_idx:]
    else:
        print("Archive comment tags not found in README.md.")

    with open(readme_file, 'w', encoding='utf-8') as f:
        f.write(readme)

if __name__ == "__main__":
    raw_events = get_recent_activity()
    parsed_acts = parse_activities(raw_events)
    
    # Generate story
    story_text = generate_story(parsed_acts)
    if not story_text:
        # Fallback story if API fails or key is missing
        story_text = "I am currently coding, learning new technologies, and building open-source projects! 💻"
        
    print(f"Generated Story: {story_text}")
    
    # Update files
    history = update_history_file(story_text)
    update_readme_files(story_text, history)
    print("README.md and history.json successfully updated!")
