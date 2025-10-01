#!/usr/bin/env python3
"""
Newsletter Email Sender for BonjourArcade

This script reads the current game of the week and sends a newsletter email
to subscribers using ConvertKit API and to one or more webhooks (e.g., Google Chat, Discord).

The announcement message is automatically read from the game's metadata.yaml file
under the 'announcement_message' field. You can also override it with --custom-message.

The script requires the game's metadata.yaml to contain:
- announcement_message: Description of the game for the newsletter
- controls: Array of control instructions for the game
- to_start: Instructions on how to start the game

Requirements:
- requests library: pip install requests
- ConvertKit account and API credentials
- Set CONVERTKIT_API_SECRET environment variable
- Set up a JSON file mapping webhook labels to env var names (see --webhook-map)
- Set the corresponding environment variables for webhook URLs

Usage:
    python send_newsletter.py [--dry-run] [--mail-api-url URL] [--mail-only] [--webhook-only] [--webhook-map webhook_map.json] [--webhook-label LABEL] [--custom-message MESSAGE]

Options:
    --mail-api-url      Override the ConvertKit API URL for sending email (default: https://api.convertkit.com/v3)
    --mail-only         Only send the email (no webhooks)
    --webhook-only      Only send to webhooks (no email)
    --webhook-map       Path to JSON file mapping webhook labels to env var names
    --webhook-label     Only send to the webhook with this label from the map
    --custom-message    Override the announcement message from metadata.yaml
    --dry-run           Show what would be sent without actually sending
"""

import json
import requests
import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
import re
import yaml
import questionary

# Configuration - Only keep what's needed
DEFAULT_API_URL = 'https://api.convertkit.com/v3'
BASE_URL = 'https://bonjourarcade-f11f7f.gitlab.io'

class NewsletterSender:
    def __init__(self, api_secret, api_url=DEFAULT_API_URL, dry_run=False, webhook_only=False, week_seed=None):
        self.api_secret = api_secret
        self.api_url = api_url
        self.dry_run = dry_run
        self.webhook_only = webhook_only
        # Compute plinko_url based on week seed or current week
        if week_seed:
            plinko_seed = week_seed
        else:
            from datetime import datetime
            now = datetime.now()
            week = now.isocalendar()[1]
            plinko_seed = f"{now.year}{week:02d}"
        self.plinko_url = f"https://felx.cc/plinko/{plinko_seed}"

    def get_previous_week_seed(self, current_seed=None):
        """Calculate the previous week's seed in YYYYWW format."""
        if current_seed:
            # Parse the current seed to get year and week
            try:
                year = int(current_seed[:4])
                week = int(current_seed[4:])
                # Go back one week
                if week == 1:
                    # If it's week 1, go to last week of previous year
                    prev_year = year - 1
                    # Calculate the last week of the previous year
                    # This is a simplified approach - in reality, the last week might be 52 or 53
                    prev_week = 52
                else:
                    prev_year = year
                    prev_week = week - 1
                return f"{prev_year}{prev_week:02d}"
            except (ValueError, IndexError):
                print(f"⚠️  Warning: Invalid seed format '{current_seed}', using current week calculation")
                pass
        
        # Fallback to current week calculation
        now = datetime.now()
        # Go back one week
        previous_week = now - timedelta(weeks=1)
        week = previous_week.isocalendar()[1]
        return f"{previous_week.year}{week:02d}"

    def get_game_from_seed(self, seed):
        """Get the game title that would be selected for a given seed using the predictions.yaml file."""
        try:
            # Read the predictions.yaml file to get the game for this seed
            predictions_path = 'public/plinko/predict/predictions.yaml'
            if not os.path.exists(predictions_path):
                print(f"⚠️  Warning: predictions.yaml not found, cannot determine previous week's game")
                return None
                
            with open(predictions_path, 'r') as f:
                predictions = yaml.safe_load(f)
            
            if not predictions:
                print(f"⚠️  Warning: predictions.yaml is empty or invalid")
                return None
            
            # Look up the game title for this seed
            # YAML parser converts string keys to integers, so we need to convert the seed to int
            try:
                seed_int = int(seed)
                game_data = predictions.get(seed_int)
            except ValueError:
                # If seed is not a valid integer, try as string
                game_data = predictions.get(seed)
            
            if not game_data:
                print(f"⚠️  Warning: No prediction found for seed {seed}")
                return None
            
            # Extract the title from the game data (which can be a dict or string)
            if isinstance(game_data, dict):
                game_title = game_data.get('title')
            else:
                # If it's already a string, use it directly
                game_title = game_data
            
            if not game_title:
                print(f"⚠️  Warning: No title found in prediction data for seed {seed}")
                return None
            
            print(f"🎯 For seed {seed}, predicted game: {game_title}")
            return game_title
            
        except Exception as e:
            print(f"⚠️  Warning: Could not determine previous week's game: {e}")
            return None

    def find_game_id_by_title(self, game_title):
        """Find a game ID in the gamelist that matches the given title."""
        try:
            gamelist_path = 'public/gamelist.json'
            if not os.path.exists(gamelist_path):
                print(f"⚠️  Warning: gamelist.json not found, cannot search for game title")
                return None
                
            with open(gamelist_path, 'r') as f:
                gamelist = json.load(f)
            
            # Search through all games for a title match
            all_games = []
            # Add games from the main games array
            if gamelist.get('games'):
                all_games.extend(gamelist['games'])
            # Add game of the week if it exists
            if gamelist.get('gameOfTheWeek') and gamelist['gameOfTheWeek'].get('id'):
                all_games.append(gamelist['gameOfTheWeek'])
            # Add previous games if they exist
            if gamelist.get('previousGames'):
                all_games.extend(gamelist['previousGames'])
            
            # Try exact match first
            for game in all_games:
                if game.get('title') == game_title:
                    return game.get('id')
            
            # Try case-insensitive match
            for game in all_games:
                if game.get('title', '').lower() == game_title.lower():
                    return game.get('id')
            
            # Try partial match (in case titles have slight differences)
            for game in all_games:
                game_title_lower = game.get('title', '').lower()
                search_title_lower = game_title.lower()
                if search_title_lower in game_title_lower or game_title_lower in search_title_lower:
                    print(f"🔍 Found partial match: '{game.get('title')}' for '{game_title}'")
                    return game.get('id')
            
            print(f"⚠️  Warning: No game found with title: {game_title}")
            return None
            
        except Exception as e:
            print(f"⚠️  Warning: Error searching for game title: {e}")
            return None

    def get_top_scores(self, game_id, top_count=3):
        """Fetch the top scores for a given game from the leaderboard API."""
        try:
            # API endpoint for fetching game scores
            api_url = 'https://us-central1-alloarcade.cloudfunctions.net/listGameScores'
            
            # Request payload
            payload = {
                'data': {
                    'timeRange': 'all',
                    'gameId': game_id
                }
            }
            
            # Headers (simplified version)
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'BonjourArcade-Newsletter/1.0'
            }
            
            if self.dry_run:
                print(f"[DRY RUN] Would fetch leaderboard for game: {game_id}")
                # Return mock data for dry run
                return [
                    {
                        'player': 'Joueur Test 1',
                        'score': 50000,
                        'rank': 1
                    },
                    {
                        'player': 'Joueur Test 2',
                        'score': 45000,
                        'rank': 2
                    },
                    {
                        'player': 'Joueur Test 3',
                        'score': 40000,
                        'rank': 3
                    }
                ]
            
            # Make the API request
            response = requests.post(api_url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if not data.get('result', {}).get('success'):
                print(f"⚠️  Warning: Leaderboard API returned unsuccessful response for {game_id}")
                return None
            
            scores = data['result'].get('scores', [])
            if not scores:
                print(f"ℹ️  No scores found for game {game_id}")
                return None
            
            # Get best score for each unique player (similar to the logic in play/index.html)
            player_best_scores = {}
            
            for score in scores:
                user_id = score.get('userId')
                current_best = player_best_scores.get(user_id)
                
                if not current_best or score.get('score', 0) > current_best.get('score', 0):
                    player_best_scores[user_id] = {
                        'player': score.get('player', 'Joueur Inconnu'),
                        'score': score.get('score', 0),
                        'rank': score.get('rank', 0)
                    }
            
            # Convert to array and sort by score (highest first)
            sorted_scores = sorted(player_best_scores.values(), key=lambda x: x.get('score', 0), reverse=True)
            
            # Return top N scores
            top_scores = sorted_scores[:top_count]
            
            # Add rank information
            for i, score in enumerate(top_scores):
                score['rank'] = i + 1
            
            return top_scores
            
        except requests.exceptions.RequestException as e:
            print(f"⚠️  Warning: Could not fetch leaderboard for {game_id}: {e}")
            return None
        except Exception as e:
            print(f"⚠️  Warning: Error processing leaderboard data for {game_id}: {e}")
            return None

    def get_last_week_highlight(self):
        """Get information about the highest score from last week's game."""
        try:
            # Get previous week's seed based on current week
            # Extract current seed from plinko_url
            current_seed = self.plinko_url.split('/')[-1]
            prev_week_seed = self.get_previous_week_seed(current_seed)
            print(f"🔍 Looking for previous week's game (seed: {prev_week_seed})...")
            
            # Get the game title for that seed from predictions.yaml
            prev_game_title = self.get_game_from_seed(prev_week_seed)
            if not prev_game_title:
                print("⚠️  Could not determine previous week's game")
                return None
            
            print(f"🎮 Previous week's game: {prev_game_title}")
            
            # Find the corresponding game ID in the gamelist
            prev_game_id = self.find_game_id_by_title(prev_game_title)
            if not prev_game_id:
                print(f"⚠️  Could not find game ID for title: {prev_game_title}")
                return None
            
            print(f"🆔 Found game ID: {prev_game_id}")
            
            # Get the top scores for that game
            top_scores = self.get_top_scores(prev_game_id, top_count=3)
            if not top_scores:
                print("⚠️  Could not fetch top scores for previous week's game")
                return None
            
            print(f"🏆 Top scores found:")
            for score in top_scores:
                medal = "🥇" if score['rank'] == 1 else "🥈" if score['rank'] == 2 else "🥉"
                print(f"  {medal} {score['player']}: {score['score']:,}")
            
            return {
                'game_id': prev_game_id,
                'game_title': prev_game_title,
                'top_scores': top_scores
            }
            
        except Exception as e:
            print(f"⚠️  Warning: Error getting last week's highlight: {e}")
            return None

    def summarize_controls(self, controls):
        """
        Summarize the controls array from metadata:
        - Only show the emoji for each control (first emoji per line)
        - Replace any number-in-square emoji (1️⃣, 2️⃣, etc) with 🔴
        - If two lines start with a joystick emoji, show 🕹️🕹️
        """
        if not controls or not isinstance(controls, list):
            return ''
        joystick_lines = [line for line in controls if str(line).strip().startswith('🕹️')]
        if len(joystick_lines) >= 2:
            return '🕹️🕹️'
        summary = ''
        for line in controls:
            line = str(line).strip()
            if not line:
                continue
            # Extract the first emoji (or character)
            first = line.split()[0]
            # Replace number-in-square emoji with 🔴
            if first in ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '0️⃣']:
                first = '🔴'
            summary += first + ' '
        return summary.strip()

    def read_game_of_the_week(self, week_seed=None):
        """Read the game of the week from predictions.yaml using the specified seed or current week's seed."""
        try:
            # Use provided seed or get current week's seed
            if week_seed:
                seed = week_seed
                print(f"🎯 Using specified week seed: {seed}")
            else:
                now = datetime.now()
                week = now.isocalendar()[1]
                seed = f"{now.year}{week:02d}"
                print(f"🎯 Using current week seed: {seed}")
            
            # Get the game title for the seed
            game_title = self.get_game_from_seed(seed)
            if not game_title:
                print(f"Error: Could not find game prediction for seed: {seed}")
                sys.exit(1)
            
            # Find the corresponding game ID in the gamelist
            game_id = self.find_game_id_by_title(game_title)
            if not game_id:
                print(f"Error: Could not find game ID for title: {game_title}")
                sys.exit(1)
            
            return game_id
            
        except Exception as e:
            print(f"Error: Could not determine game of the week: {e}")
            sys.exit(1)

    def get_current_week_game_title(self):
        """Get the current week's game title from predictions.yaml."""
        try:
            # Get current week's seed
            now = datetime.now()
            week = now.isocalendar()[1]
            current_seed = f"{now.year}{week:02d}"
            
            # Get the game title for the current seed
            game_title = self.get_game_from_seed(current_seed)
            if not game_title:
                print(f"Error: Could not find game prediction for current week (seed: {current_seed})")
                return None
            
            return game_title
            
        except Exception as e:
            print(f"Error: Could not determine current week's game title: {e}")
            return None

    def get_week_game_by_seed(self, seed):
        """Get the game title for a specific week seed from predictions.yaml."""
        try:
            game_title = self.get_game_from_seed(seed)
            if not game_title:
                print(f"Error: Could not find game prediction for seed: {seed}")
                return None
            
            return game_title
            
        except Exception as e:
            print(f"Error: Could not determine game for seed {seed}: {e}")
            return None
    
    def read_game_metadata(self, game_id):
        """Read metadata from public/games/{gameid}/metadata.yaml."""
        meta_path = f'public/games/{game_id}/metadata.yaml'
        try:
            with open(meta_path, 'r') as f:
                meta = yaml.safe_load(f)
            
            # Validate required fields
            missing_fields = []
            if not meta.get('controls'):
                missing_fields.append('controls')
            if not meta.get('to_start'):
                missing_fields.append('to_start')
            
            if missing_fields:
                print(f"❌ ERROR: Game of the week metadata is missing required fields: {', '.join(missing_fields)}")
                print(f"📁 File: {meta_path}")
                print("📝 These fields are required for the newsletter to be sent:")
                if 'controls' in missing_fields:
                    print("   - controls: Array of control instructions for the game")
                if 'to_start' in missing_fields:
                    print("   - to_start: Instructions on how to start the game")
                print("\n🛑 Aborting newsletter send to allow you to add the missing fields.")
                print("\n💡 Example of what to add to metadata.yaml:")
                if 'controls' in missing_fields:
                    print("   controls:")
                    print("     - '🕹️ Use arrow keys to move'")
                    print("     - '🔴 Press SPACE to jump'")
                if 'to_start' in missing_fields:
                    print("   to_start: 'Press START or click the play button to begin'")
                print(f"\n📋 Current metadata structure for {game_id}:")
                for key, value in meta.items():
                    if key in missing_fields:
                        print(f"   {key}: [MISSING]")
                    else:
                        print(f"   {key}: {value}")
                sys.exit(1)
            
            return meta
        except FileNotFoundError:
            print(f"Error: Could not find metadata file for game {game_id}: {meta_path}")
            sys.exit(1)
        except yaml.YAMLError as e:
            print(f"Error: Invalid YAML in metadata file for game {game_id}: {e}")
            sys.exit(1)
    
    def create_email_content(self, game_id, meta, custom_message=None, last_week_highlight=None):
        """
        Create email content for the newsletter.
        
        Note: This method assumes that meta['controls'] and meta['to_start'] are present
        and have values, as they are validated in read_game_metadata().
        """
        from datetime import datetime
        import re
        cover_url = f'{BASE_URL}/games/{game_id}/cover.png'
        play_url = f'https://felx.cc/b/{game_id}'
        leaderboard_url = f'https://alloarcade.web.app/leaderboards/{game_id}'
        title = meta.get('title', game_id)
        # Remove parenthetical content for display in email body
        clean_title = re.sub(r'\s*\([^)]*\)', '', title).strip()
        developer = meta.get('developer', 'Inconnu')
        year = meta.get('year', 'Inconnue')
        genre = meta.get('genre', 'Non spécifié')
        controls = self.summarize_controls(meta.get('controls'))
        description = clean_title
        subject = f'🕹️ Jeu de la semaine - {title}'
        
        # Create last week's highlight section if available
        last_week_html = ''
        if last_week_highlight:
            # Create the top scores list with medals
            scores_list = ''
            for score in last_week_highlight['top_scores']:
                medal = "🥇" if score['rank'] == 1 else "🥈" if score['rank'] == 2 else "🥉"
                scores_list += f'<li style="margin:8px 0;"><strong>{medal} {score["player"]}</strong>: {score["score"]:,} points</li>'
            
            last_week_html = f'''
        <div style="background:#f8f9fa;border-left:4px solid #007bff;padding:16px;margin:18px 0;border-radius:4px;">
            <h3 style="margin:0 0 12px 0;color:#007bff;">🏆 Top scores de la semaine dernière sur {last_week_highlight['game_title']}</h3>
            <ul style="margin:0;padding-left:20px;font-size:1.1em;">
                {scores_list}
            </ul>
        </div>'''
        
        # Get announcement message from metadata, fallback to custom_message if provided
        announcement_message = meta.get('announcement_message', '') or custom_message or ''
        
        # Validate that we have an announcement message
        if not announcement_message.strip():
            raise ValueError("Announcement message is empty. Cannot create email content without an announcement.")
        
        custom_html = f'<div style="margin-bottom:18px;font-size:1.1em;">{announcement_message}</div>' if announcement_message else ''
        html_content = f'''
        <html><body>
        <h1 style="color:#333;text-align:center;margin-bottom:30px;">🎮 Annonce du jeu de la semaine!</h1>
        
        <div style="background:#f0f8ff;border:2px solid #007bff;border-radius:8px;padding:20px;margin:20px 0;">
            <h2 style="color:#007bff;margin-top:0;">🎯 Jeu de la semaine : {clean_title}</h2>
            
            <!-- Description du jeu -->
            <div style="margin-bottom:20px;font-size:1.1em;line-height:1.6;">
                {announcement_message}
            </div>
            
            <!-- Layout responsive en deux colonnes -->
            <div style="display:flex;flex-direction:row;gap:20px;align-items:flex-start;">
                <div style="flex:1;min-width:0;">
                    <ul style="margin:0;padding-left:20px;font-size:1.1em;">
                        <li><b>Développeur :</b> {developer}</li>
                        <li><b>Année :</b> {year}</li>
                        <li><b>Genre :</b> {genre}</li>
                        <li><b>Contrôles :</b> {controls}</li>
                    </ul>
                </div>
                <div style="flex:1;min-width:0;text-align:center;">
                    <img src="{cover_url}" alt="Cover de {clean_title}" style="max-width:100%;height:auto;border-radius:8px;box-shadow:0 4px 8px rgba(0,0,0,0.1);" />
                </div>
            </div>
            
            <!-- Media query pour mobile -->
            <style>
                @media (max-width: 600px) {{
                    .game-section {{
                        flex-direction: column !important;
                    }}
                    .game-section > div {{
                        flex: none !important;
                        width: 100% !important;
                        margin-bottom: 15px;
                    }}
                    .game-section > div:last-child {{
                        margin-bottom: 0;
                    }}
                }}
            </style>
        </div>
        
        <div style="text-align:center;margin:30px 0;">
            <a href="{play_url}" style="background:#007bff;color:white;padding:15px 30px;text-decoration:none;border-radius:5px;font-size:18px;font-weight:bold;margin-right:15px;display:inline-block;margin-bottom:10px;">🎮 Jouer maintenant !</a>
            <a href="{leaderboard_url}" style="background:#ffc107;color:#212529;padding:15px 30px;text-decoration:none;border-radius:5px;font-size:18px;font-weight:bold;display:inline-block;margin-bottom:10px;">🏆 Classements</a>
        </div>
        
        {last_week_html}
        
        <p style="text-align:center;color:#666;font-style:italic;">Bonne semaine ! ☀️</p>
        </body></html>
        '''
        return {
            'description': description,
            'subject': subject,
            'content': html_content
        }
    
    def send_email(self, content):
        """Send the email using ConvertKit API."""
        if self.dry_run:
            print('=== DRY RUN MODE ===')
            print('Subject:', content['subject'])
            print('Description:', content['description'])
            print('HTML Content:', content['content'])
            return True
        
        from datetime import datetime, timedelta, timezone
        send_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(timespec='seconds').replace('+00:00', 'Z')
        
        data = {
            'api_secret': self.api_secret,
            'description': content['description'],
            'subject': content['subject'],
            'send_at': send_at,
            'content': content['content']
        }
        
        url = f'{self.api_url}/broadcasts'
        headers = {'Content-Type': 'application/json'}
        
        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            
            print('API response code:', response.status_code)
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error sending email: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response: {e.response.text}")
                print(f"Response status: {e.response.status_code}")
                print(f"Response headers: {dict(e.response.headers)}")
                
                # Additional debugging for 401 errors
                if e.response.status_code == 401:
                    print("\n🔍 401 Unauthorized Error Debug:")
                    print("   This usually means the API secret is invalid or malformed.")
                    print("   Common causes in CI/CD:")
                    print("   1. Variable masking issues in GitLab")
                    print("   2. Trailing whitespace/newlines")
                    print("   3. Variable not properly substituted")
                    print("   4. Wrong API secret (test vs production)")
                    print(f"   Current API secret length: {len(self.api_secret)}")
                    print(f"   API secret starts with: {self.api_secret[:4]}...")
                    print(f"   API secret ends with: ...{self.api_secret[-4:]}")
                    
                    # Try to validate the API secret format
                    if not self.api_secret.replace('_', '').isalnum():
                        print("   ⚠️  API secret contains non-alphanumeric characters (except underscores)")
                    if len(self.api_secret) < 20:
                        print("   ⚠️  API secret seems too short")
                    if len(self.api_secret) > 50:
                        print("   ⚠️  API secret seems too long")
            return False
    
    def test_api_credentials(self):
        """Test ConvertKit API credentials by making a simple API call."""
        print("🧪 Testing ConvertKit API credentials...")
        
        # Test with a simple API call to get account info
        test_url = f'{self.api_url}/account'
        headers = {'Content-Type': 'application/json'}
        data = {'api_secret': self.api_secret}
        
        try:
            response = requests.get(test_url, headers=headers, params=data, timeout=10)
            
            print(f"📡 API Test Response:")
            print(f"   Status Code: {response.status_code}")
            print(f"   Response Headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                print("✅ API credentials are valid!")
                try:
                    account_data = response.json()
                    if 'account' in account_data:
                        account = account_data['account']
                        print(f"   Account Name: {account.get('name', 'N/A')}")
                        print(f"   Account ID: {account.get('id', 'N/A')}")
                        print(f"   Primary Email: {account.get('primary_email_address', 'N/A')}")
                except:
                    print("   (Could not parse account data)")
                return True
            else:
                print(f"❌ API credentials test failed!")
                print(f"   Response: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Error testing API credentials: {e}")
            return False
    
    def send_webhook(self, content, game_id, meta, webhook_map_path=None, filter_label=None, custom_message=None, last_week_highlight=None):
        """Send a plaintext version of the newsletter to one or more webhooks, using a JSON map of label:{env,type}. Optionally filter by label."""
        import requests
        import os
        import json
        if webhook_map_path is None:
            webhook_map_path = "webhook_map.json"
        # Read webhook map JSON file
        if not os.path.exists(webhook_map_path):
            print(f"⚠️  Webhook map file '{webhook_map_path}' not found. Skipping webhook notification.")
            return
        with open(webhook_map_path, "r") as f:
            try:
                webhook_map = json.load(f)
            except Exception as e:
                print(f"⚠️  Failed to parse webhook map JSON: {e}. Skipping webhook notification.")
                return
        play_url = f'https://felx.cc/b/{game_id}'
        cover_url = f'{BASE_URL}/games/{game_id}/cover.png'
        leaderboard_url = f'https://alloarcade.web.app/leaderboards/{game_id}'
        title = meta.get('title', game_id)
        developer = meta.get('developer', 'Inconnu')
        year = meta.get('year', 'Inconnue')
        genre = meta.get('genre', 'Non spécifié')
        controls = self.summarize_controls(meta.get('controls'))
        
        # Create last week's highlight text if available
        last_week_text = ''
        if last_week_highlight:
            # Create the top scores list with medals
            scores_list = ''
            for score in last_week_highlight['top_scores']:
                medal = "🥇" if score['rank'] == 1 else "🥈" if score['rank'] == 2 else "🥉"
                scores_list += f"{medal} {score['player']}: {score['score']:,} points\n"
            
            last_week_text = f"""
Top scores de la semaine dernière sur {last_week_highlight['game_title']} :
{scores_list}"""
        
        # Get announcement message from metadata, fallback to custom_message if provided
        announcement_message = meta.get('announcement_message', '') or custom_message or ''
        
        # Validate that we have an announcement message
        if not announcement_message.strip():
            raise ValueError("Announcement message is empty. Cannot send webhook without an announcement.")
        
        custom_text = f"{announcement_message}\n\n" if announcement_message else ''
        # Message template with {b} for bold, now includes plinko link and last week's highlight
        message_template = f"""
Annonce du jeu de la semaine!
{custom_text}{{b}}Jeu de la semaine :{{b}} {title}
{{b}}Développeur :{{b}} {developer}
{{b}}Année :{{b}} {year}
{{b}}Genre :{{b}} {genre}
{{b}}Contrôles :{{b}} {controls}
{{b}}Image :{{b}} {cover_url}
{{b}}Classements :{{b}} {leaderboard_url}

🕹️ {{b}}Faites-en l'essai :{{b}} {play_url}
{last_week_text}
Bonne semaine ! ☀️
""".strip()
        sent_any = False
        # If filter_label is set, only use that label
        if filter_label:
            if filter_label not in webhook_map:
                print(f"⚠️  Webhook label '{filter_label}' not found in map. Skipping webhook notification.")
                return
            items = [(filter_label, webhook_map[filter_label])]
        else:
            items = webhook_map.items()
        if self.dry_run:
            print("=== DRY RUN MODE (WEBHOOKS) ===")
            for label, info in items:
                env_var = info.get('env')
                wtype = info.get('type')
                url = os.getenv(env_var) if env_var else None
                if not url:
                    print(f"⚠️  Env var '{env_var}' for webhook label '{label}' is not set. Skipping.")
                    continue
                if wtype == 'discord':
                    bold = '**'
                    payload = {"content": message_template.replace('{b}', bold)}
                elif wtype == 'googlechat':
                    bold = '*'
                    payload = {"text": message_template.replace('{b}', bold)}
                else:
                    print(f"⚠️  Unknown webhook type '{wtype}' for label '{label}'. Skipping.")
                    continue
                print(f"[DRY RUN] Would send webhook to '{label}' (env: {env_var}, type: {wtype}, url: {url}):\n{payload}\n")
                sent_any = True
            if not sent_any:
                print("⚠️  No webhook messages would be sent (no valid URLs found).")
            return
        for label, info in items:
            env_var = info.get('env')
            wtype = info.get('type')
            url = os.getenv(env_var) if env_var else None
            if not url:
                print(f"⚠️  Env var '{env_var}' for webhook label '{label}' is not set. Skipping.")
                continue
            if wtype == 'discord':
                bold = '**'
                payload = {"content": message_template.replace('{b}', bold)}
            elif wtype == 'googlechat':
                bold = '*'
                payload = {"text": message_template.replace('{b}', bold)}
            else:
                print(f"⚠️  Unknown webhook type '{wtype}' for label '{label}'. Skipping.")
                continue
            try:
                resp = requests.post(url, json=payload)
                resp.raise_for_status()
                print(f"✅ Webhook message sent to '{label}' (env: {env_var}, type: {wtype})")
                sent_any = True
            except requests.exceptions.RequestException as e:
                print(f"❌ Error sending webhook to '{label}' (env: {env_var}, type: {wtype}): {e}")
                if hasattr(e, 'response') and e.response:
                    print(f"Response: {e.response.text}")
        if not sent_any:
            print("⚠️  No webhook messages sent (no valid URLs found).")

    def run(self, webhook_map_path=None, filter_label=None, mail_only=False, custom_message=None, week_seed=None):
        """
        Run the newsletter process with the following safety rules:
        - If webhook_only=True: Send webhooks (respecting filter_label) and skip email
        - If mail_only=True: Send only the email (no webhooks)
        - If neither flag is set: Send both webhooks and email
        - If dry_run=True: Skip ConvertKit API call, but still generate and preview content
        """
        print('📧 Starting newsletter email process...')
        
        # Read game data
        print("📖 Reading game of the week...")
        game_id = self.read_game_of_the_week(week_seed)
        print(f'✅ Game of the week: {game_id}')
        
        # Read metadata
        print("📖 Reading game metadata...")
        meta = self.read_game_metadata(game_id)
        print('✅ Metadata:')
        for k, v in meta.items():
            print(f'  - {k}: {v}')
        
        # Get last week's highlight
        print("🏆 Getting last week's highlight...")
        last_week_highlight = self.get_last_week_highlight()
        if last_week_highlight:
            print(f"✅ Last week's highlight: Top {len(last_week_highlight['top_scores'])} scores on {last_week_highlight['game_title']}")
        else:
            print("ℹ️  No last week's highlight available")
        
        # Generate email content
        print("✍️  Generating email content...")
        content = self.create_email_content(game_id, meta, custom_message=custom_message, last_week_highlight=last_week_highlight)
        print(f'✅ Email content ready: {content["subject"]}')
        
        # Webhook-only: send webhooks and exit before email
        if self.webhook_only:
            self.send_webhook(
                content, game_id, meta,
                webhook_map_path=webhook_map_path,
                filter_label=filter_label,
                custom_message=custom_message,
                last_week_highlight=last_week_highlight
            )
            print("🛑 Webhook-only mode: Skipping email send.")
            return
        
        # If not mail-only, send webhooks (normal case: both)
        if not mail_only:
            self.send_webhook(
                content, game_id, meta,
                webhook_map_path=webhook_map_path,
                filter_label=filter_label,
                custom_message=custom_message,
                last_week_highlight=last_week_highlight
            )
        
        # Mail-only: do NOT return early; proceed to email sending only
        # Send email (but respect dry_run flag)
        if not self.dry_run:
            print("📤 Sending email...")
            success = self.send_email(content)
            if success:
                print("🎉 Newsletter sent successfully!")
            else:
                print("💥 Failed to send newsletter")
                sys.exit(1)
        else:
            print("🛑 DRY RUN MODE: Skipping email send.")
            # Print HTML content for preview when ConvertKit is selected
            print("\n" + "="*50)
            print("📧 EMAIL HTML PREVIEW (DRY RUN)")
            print("="*50)
            print(content['content'])
            print("="*50)

def main():
    parser = argparse.ArgumentParser(description='Send BonjourArcade newsletter')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Show what would be sent without actually sending')
    parser.add_argument('--mail-api-url', default=DEFAULT_API_URL,
                       help='ConvertKit API URL (for sending email/broadcasts)')
    parser.add_argument('--webhook-only', action='store_true',
                       help='Send only to webhook and skip email (for testing)')
    parser.add_argument('--mail-only', action='store_true',
                       help='Send only the email (no webhooks)')
    parser.add_argument('--webhook-map', default='webhook_map.json',
                       help='Path to JSON file mapping webhook labels to env var names (default: webhook_map.json)')
    parser.add_argument('--webhook-label', default=None, type=str,
                       help='Only send to the webhook with this label from the map (for testing)')
    parser.add_argument('--custom-message', default=None, type=str,
                      help='Override the announcement message from metadata.yaml (appears at the top of the email and webhook)')
    parser.add_argument('--week-seed', default=None, type=str,
                      help='Specific week seed (YYYYWW format) to use instead of current week (useful for testing or past weeks)')
    parser.add_argument('--test-api', action='store_true',
                      help='Test API credentials without sending newsletter (useful for debugging authentication issues)')
    
    args = parser.parse_args()

    # Use custom message from command line if provided, otherwise it will be read from metadata
    custom_message = args.custom_message

    api_secret = os.getenv('CONVERTKIT_API_SECRET')
    if not api_secret:
        print('❌ Error: API secret is required. Set CONVERTKIT_API_SECRET environment variable.')
        sys.exit(1)
    
    # Debug: Check API secret format (without exposing the actual secret)
    print(f"🔍 API Secret Debug Info:")
    print(f"   - Length: {len(api_secret)} characters")
    print(f"   - Starts with: {api_secret[:4]}...")
    print(f"   - Ends with: ...{api_secret[-4:]}")
    print(f"   - Contains only alphanumeric chars: {api_secret.replace('_', '').isalnum()}")
    print(f"   - Contains underscores: {'_' in api_secret}")
    
    # Check for common GitLab CI/CD issues
    if api_secret.startswith('$'):
        print("⚠️  WARNING: API secret appears to be a variable reference (starts with $)")
        print("   This might indicate the environment variable wasn't properly substituted.")
    if api_secret.endswith('\n') or api_secret.endswith('\r'):
        print("⚠️  WARNING: API secret has trailing newline/carriage return")
        print("   This can happen when copying from certain text editors.")
        api_secret = api_secret.strip()
    if ' ' in api_secret:
        print("⚠️  WARNING: API secret contains spaces")
        print("   This might indicate improper quoting in the CI/CD configuration.")
    
    # EARLY VALIDATION: Check if we have an announcement message and required metadata fields before any user interaction
    if not custom_message:
        print("🔍 Checking game of the week metadata...")
        try:
            # Create a temporary sender to check the metadata
            temp_sender = NewsletterSender(
                api_secret=api_secret,
                api_url=args.mail_api_url,
                dry_run=True,  # Use dry run to avoid any actual sending
                webhook_only=False,
                week_seed=args.week_seed
            )
            
            # Read game data and metadata to check announcement and required fields
            game_id = temp_sender.read_game_of_the_week(args.week_seed)
            meta = temp_sender.read_game_metadata(game_id)
            
            # Check announcement message
            announcement_message = meta.get('announcement_message', '')
            if not announcement_message.strip():
                print("❌ ERROR: The announcement message for the game of the week is empty!")
                print("📝 Please add an 'announcement_message' field to the metadata.yaml file")
                print(f"   File: public/games/{game_id}/metadata.yaml")
                print("   Or use --custom-message to provide a message via command line.")
                print("\n🛑 Aborting newsletter send to allow you to write the announcement.")
                print("\n💡 Example of what to add to metadata.yaml:")
                print("   announcement_message: \"Ce jeu classique de plateforme vous emmène dans une aventure...\"")
                print("\n💡 Or run with: --custom-message \"Your announcement text here\"")
                print("\n📝 The announcement message should describe why this game is special,")
                print("   what makes it fun, or any interesting facts about it.")
                print("   This text appears prominently at the top of the newsletter.")
                print(f"\n📋 Current metadata structure for {game_id}:")
                for key, value in meta.items():
                    if key == 'announcement_message':
                        print(f"   {key}: {'[EMPTY]' if not value else value[:50] + '...' if len(str(value)) > 100 else value}")
                    else:
                        print(f"   {key}: {value}")
                sys.exit(1)
            
            print(f"✅ Announcement message found: {announcement_message[:100]}{'...' if len(announcement_message) > 100 else ''}")
            print("✅ Required metadata fields (controls, to_start) are present")
            
        except Exception as e:
            print(f"⚠️  Warning: Could not validate metadata early: {e}")
            print("   Will check again during the main process...")
    
    # Interactive webhook selection if no --webhook-label is provided
    selected_webhook_labels = None
    if args.webhook_label is None and not args.mail_only:
        webhook_map_path = args.webhook_map
        if not os.path.exists(webhook_map_path):
            print(f"⚠️  Webhook map file '{webhook_map_path}' not found. Skipping webhook selection.")
        else:
            with open(webhook_map_path, "r") as f:
                try:
                    webhook_map = json.load(f)
                except Exception as e:
                    print(f"⚠️  Failed to parse webhook map JSON: {e}. Skipping webhook selection.")
                    webhook_map = None
            if webhook_map:
                choices = list(webhook_map.keys())
                # Add ConvertKit Email as a selectable option
                MAILING_LIST_LABEL = "ConvertKit Email"
                choices.insert(0, MAILING_LIST_LABEL)
                selected = questionary.checkbox(
                    "Sélectionnez les webhooks auxquels envoyer :",
                    choices=choices
                ).ask()
                if not selected:
                    print("Aucun webhook sélectionné. Abandon.")
                    sys.exit(0)
                selected_webhook_labels = selected
    elif args.webhook_label is not None:
        selected_webhook_labels = [args.webhook_label]
    elif args.mail_only:
        # In mail-only mode, we don't need webhook selection
        selected_webhook_labels = None

    sender = NewsletterSender(
        api_secret=api_secret,
        api_url=args.mail_api_url,
        dry_run=args.dry_run,
        webhook_only=args.webhook_only,
        week_seed=args.week_seed
    )
    
    # Handle API testing mode
    if args.test_api:
        print("🧪 API Testing Mode - Testing credentials only")
        success = sender.test_api_credentials()
        if success:
            print("🎉 API credentials test passed!")
            sys.exit(0)
        else:
            print("💥 API credentials test failed!")
            sys.exit(1)
    
    # If selected_webhook_labels is set, send to each label in turn
    if selected_webhook_labels is not None:
        MAILING_LIST_LABEL = "ConvertKit Email"
        # If ConvertKit Email is selected, send ONLY the email
        if MAILING_LIST_LABEL in selected_webhook_labels:
            sender.run(
                webhook_map_path=args.webhook_map,
                filter_label=None,
                mail_only=True,     # Email only
                custom_message=custom_message,
                week_seed=args.week_seed
            )
            # Remove it from the list so it's not treated as a webhook
            selected_webhook_labels = [lbl for lbl in selected_webhook_labels if lbl != MAILING_LIST_LABEL]
        
        # Send each selected webhook as webhook-only runs
        for label in selected_webhook_labels or []:
            # For each webhook, run in webhook-only mode so no email is sent
            sender.webhook_only = True
            sender.run(
                webhook_map_path=args.webhook_map,
                filter_label=label,
                mail_only=False,
                custom_message=custom_message,
                week_seed=args.week_seed
            )
            # Reset webhook_only flag for safety
            sender.webhook_only = args.webhook_only
    else:
        # In non-interactive mode, respect flags
        if args.dry_run:
            print("🛑 DRY RUN MODE: Skipping ConvertKit email send.")
        if args.webhook_only:
            sender.run(
                webhook_map_path=args.webhook_map,
                filter_label=args.webhook_label,
                mail_only=False,
                custom_message=custom_message,
                week_seed=args.week_seed
            )
        elif args.mail_only or (not args.webhook_label and not args.webhook_only):
            # Default to email only if no webhook label is specified and not webhook-only
            sender.run(
                webhook_map_path=args.webhook_map,
                filter_label=None,
                mail_only=True,
                custom_message=custom_message,
                week_seed=args.week_seed
            )

if __name__ == '__main__':
    main() 
