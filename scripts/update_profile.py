import os
import sys
import json
import base64
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

def load_env():
    # Robust env file parser that handles both ":" and "=" formats
    if os.path.exists('.env'):
        with open('.env', 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    k, v = line.split('=', 1)
                elif ':' in line:
                    k, v = line.split(':', 1)
                else:
                    continue
                os.environ[k.strip()] = v.strip()

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
            "Keep it to exactly 1 sentence, write it in first-person ('I...'), and do NOT include any emojis. "
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
- Do NOT use any emojis or markdown code blocks. Just output the plain text diary entry.
- Do NOT make things up; stick strictly to the actual code changes shown in the commits.
"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_api_key}"
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

def get_github_language_stats():
    headers = {
        'Accept': 'application/vnd.github+json'
    }
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token:
        headers['Authorization'] = f'token {github_token}'
        
    repos_url = 'https://api.github.com/users/virajverse/repos?sort=updated&per_page=15'
    try:
        response = requests.get(repos_url, headers=headers)
        if response.status_code != 200:
            print(f"Error fetching repos for languages: {response.status_code}")
            return None
        repos = response.json()
        
        lang_bytes = {}
        for repo in repos:
            if repo.get('fork'):
                continue
            name = repo.get('name')
            lang_url = f'https://api.github.com/repos/virajverse/{name}/languages'
            lang_r = requests.get(lang_url, headers=headers)
            if lang_r.status_code == 200:
                repo_langs = lang_r.json()
                for lang, bytes_count in repo_langs.items():
                    lang_bytes[lang] = lang_bytes.get(lang, 0) + bytes_count
            
        if not lang_bytes:
            return None
            
        total_bytes = sum(lang_bytes.values())
        sorted_langs = sorted(lang_bytes.items(), key=lambda x: x[1], reverse=True)
        
        stats = []
        other_bytes = 0
        for i, (lang, bytes_count) in enumerate(sorted_langs):
            pct = (bytes_count / total_bytes) * 100
            if i < 4:
                stats.append((lang, pct))
            else:
                other_bytes += bytes_count
                
        if other_bytes > 0:
            stats.append(("Other", (other_bytes / total_bytes) * 100))
            
        return stats
    except Exception as e:
        print(f"Exception calculating language stats: {e}")
        return None

def generate_languages_svg(stats):
    if not stats:
        stats = [
            ("TypeScript", 40.0),
            ("JavaScript", 20.0),
            ("Python", 15.0),
            ("Go", 10.0),
            ("Rust", 7.0),
            ("HTML/CSS", 5.0),
            ("Other", 3.0)
        ]
        
    radii = [60, 46, 32]
    colors = ["#8b5cf6", "#f59e0b", "#ec4899", "#10b981", "#3b82f6", "#f43f5e", "#6b7280"]
    
    circle_elements = ""
    for i, r in enumerate(radii):
        if i >= len(stats):
            break
        lang, pct = stats[i]
        circumference = 2 * 3.14159 * r
        dash_len = (pct / 100.0) * circumference
        gap_len = circumference - dash_len
        color = colors[i]
        
        circle_elements += f'  <circle cx="120" cy="110" r="{r}" fill="none" stroke="#1f242c" stroke-width="8" />\n'
        circle_elements += f'  <circle cx="120" cy="110" r="{r}" fill="none" stroke="{color}" stroke-width="8" stroke-dasharray="{dash_len:.2f}, {gap_len:.2f}" stroke-linecap="round" transform="rotate(-90 120 110)" />\n\n'
        
    legend_elements = ""
    for i, (lang, pct) in enumerate(stats):
        color = colors[i] if i < len(colors) else "#6b7280"
        y = 15 + i * 20
        legend_elements += f'    <circle cx="10" cy="{y}" r="5" fill="{color}" />\n'
        legend_elements += f'    <text x="22" y="{y+4}" fill="#c9d1d9">{lang} <tspan fill="#8b949e">{pct:.1f}%</tspan></text>\n\n'
        
    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" width="360" height="200" viewBox="0 0 360 200">
  <rect width="358" height="198" rx="8" x="1" y="1" fill="#0d1117" stroke="#30363d" stroke-width="1" />
  <text x="180" y="25" text-anchor="middle" font-family="monospace" font-size="12" font-weight="bold" fill="#7ee787">SYSTEM CORE LANGUAGES</text>
  
  <!-- Concentric Circles (Orbits) -->
{circle_elements}
  <!-- Legend -->
  <g transform="translate(210, 45)" font-family="monospace" font-size="11" fill="#c9d1d9">
{legend_elements}  </g>
</svg>
"""
    with open("languages.svg", "w", encoding="utf-8") as f:
        f.write(svg_content)
    print("languages.svg dynamically generated successfully.")

def update_history_file(new_story):
    today_str = datetime.utcnow().strftime('%Y-%m-%d')
    history_file = 'history.json'
    
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except Exception:
            history = []
    else:
        history = []
        
    duplicate = False
    for entry in history:
        if entry.get('date') == today_str and entry.get('story') == new_story:
            duplicate = True
            break
            
    if not duplicate:
        history.insert(0, {
            'date': today_str,
            'story': new_story
        })
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

    # 1. Update AI Diary
    now_iso = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    diary_content = f"\n\n> <img src=\"https://api.iconify.design/lucide/bot.svg?color=%2300b894\" width=\"16\" height=\"16\" valign=\"middle\" /> **Developer Active Session** (Updated <relative-time datetime=\"{now_iso}\">{now_iso}</relative-time>):\n> *\"{story}\"*\n\n"
    
    start_tag = '<!-- START_SECTION:ai-diary -->'
    end_tag = '<!-- END_SECTION:ai-diary -->'
    
    if start_tag in readme and end_tag in readme:
        start_idx = readme.find(start_tag) + len(start_tag)
        end_idx = readme.find(end_tag)
        readme = readme[:start_idx] + diary_content + readme[end_idx:]

    # 2. Update Archive
    archive_html = "\n\n<details>\n  <summary><img src=\"https://api.iconify.design/lucide/history.svg?color=%230984e3\" width=\"16\" height=\"16\" valign=\"middle\" /> View Past Workspace Logs</summary>\n  <ul>\n"
    for entry in history_list[1:10]:
        archive_html += f"    <li><strong>{entry['date']}:</strong> {entry['story']}</li>\n"
    archive_html += "  </ul>\n</details>\n\n"
    
    archive_start = '<!-- START_SECTION:ai-diary-archive -->'
    archive_end = '<!-- END_SECTION:ai-diary-archive -->'
    
    if archive_start in readme and archive_end in readme:
        start_idx = readme.find(archive_start) + len(archive_start)
        end_idx = readme.find(archive_end)
        readme = readme[:start_idx] + archive_html + readme[end_idx:]

    with open(readme_file, 'w', encoding='utf-8') as f:
        f.write(readme)

if __name__ == "__main__":
    load_env()
    
    # 1. Fetch GitHub and generate AI story
    raw_events = get_recent_activity()
    parsed_acts = parse_activities(raw_events)
    story_text = generate_story(parsed_acts)
    if not story_text:
        story_text = "I am currently coding, learning new technologies, and building open-source projects!"
        
    print(f"Generated Story: {story_text}")
    
    # 2. Update history list and readme
    history = update_history_file(story_text)
    update_readme_files(story_text, history)
    
    # 3. Calculate GitHub language stats and write languages.svg dynamically
    lang_stats = get_github_language_stats()
    generate_languages_svg(lang_stats)
    
    print("README.md, history.json, and languages.svg successfully updated!")
