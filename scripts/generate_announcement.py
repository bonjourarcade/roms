#!/usr/bin/env python3
"""
AI-Powered Announcement Generator for BonjourArcade

This script automatically generates French announcement messages for games of the week
using AI services like OpenAI GPT or Claude. It reads the game metadata and generates
a compelling description limited to 4 sentences.

Requirements:
- OpenAI API key (set OPENAI_API_KEY environment variable)
- Or Anthropic API key (set ANTHROPIC_API_KEY environment variable)
- requests library: pip install requests

Usage:
    python generate_announcement.py [--week-seed YYYYWW] [--next-week] [--ai-service openai|claude] [--update-metadata] [--dry-run]

Options:
    --week-seed         Specific week seed (YYYYWW format) to use instead of current week
    --next-week         Use next week's seed instead of current week (useful when you don't know the current week number)
    --ai-service        AI service to use: 'openai' or 'claude' (default: openai)
    --update-metadata   Automatically update the metadata.yaml file with the generated announcement
    --dry-run           Show what would be generated without actually updating files
"""

import json
import requests
import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
import yaml
import re

# Configuration
DEFAULT_AI_SERVICE = 'openai'
MAX_SENTENCES = 3  # Maximum sentences for announcement messages
OPENAI_API_URL = 'https://api.openai.com/v1/chat/completions'
ANTHROPIC_API_URL = 'https://api.anthropic.com/v1/messages'

class AnnouncementGenerator:
    def __init__(self, ai_service='openai', dry_run=False):
        self.ai_service = ai_service.lower()
        self.dry_run = dry_run
        
        # In dry-run mode, we don't need API keys
        if self.dry_run:
            return
        
        # Set API key based on service
        if self.ai_service == 'openai':
            self.api_key = os.getenv('OPENAI_API_KEY')
            if not self.api_key:
                print('❌ Error: OPENAI_API_KEY environment variable is required for OpenAI service.')
                sys.exit(1)
        elif self.ai_service == 'claude':
            self.api_key = os.getenv('ANTHROPIC_API_KEY')
            if not self.api_key:
                print('❌ Error: ANTHROPIC_API_KEY environment variable is required for Claude service.')
                sys.exit(1)
        else:
            print(f'❌ Error: Unsupported AI service: {ai_service}. Use "openai" or "claude".')
            sys.exit(1)

    def get_current_week_seed(self):
        """Get current week's seed in YYYYWW format."""
        now = datetime.now()
        week = now.isocalendar()[1]
        return f"{now.year}{week:02d}"

    def get_next_week_seed(self):
        """Get next week's seed in YYYYWW format."""
        now = datetime.now()
        # Add 7 days to get next week
        next_week = now + timedelta(days=7)
        week = next_week.isocalendar()[1]
        return f"{next_week.year}{week:02d}"

    def get_game_from_seed(self, seed):
        """Get the game title that would be selected for a given seed using the predictions.yaml file."""
        try:
            predictions_path = 'public/plinko/predict/predictions.yaml'
            if not os.path.exists(predictions_path):
                print(f"❌ Error: predictions.yaml not found at {predictions_path}")
                sys.exit(1)
                
            with open(predictions_path, 'r') as f:
                predictions = yaml.safe_load(f)
            
            if not predictions:
                print(f"❌ Error: predictions.yaml is empty or invalid")
                sys.exit(1)
            
            # Look up the game title for this seed
            try:
                seed_int = int(seed)
                game_data = predictions.get(seed_int)
            except ValueError:
                game_data = predictions.get(seed)
            
            if not game_data:
                print(f"❌ Error: No prediction found for seed {seed}")
                sys.exit(1)
            
            # Extract title from the game data (could be dict or string)
            if isinstance(game_data, dict):
                game_title = game_data.get('title')
            else:
                game_title = game_data
            
            if not game_title:
                print(f"❌ Error: No title found in prediction data for seed {seed}")
                sys.exit(1)
            
            print(f"🎯 For seed {seed}, predicted game: {game_title}")
            return game_title
            
        except Exception as e:
            print(f"❌ Error: Could not determine game for seed {seed}: {e}")
            sys.exit(1)

    def find_game_id_by_title(self, game_title):
        """Find a game ID in the gamelist that matches the given title."""
        try:
            gamelist_path = 'public/gamelist.json'
            if not os.path.exists(gamelist_path):
                print(f"❌ Error: gamelist.json not found at {gamelist_path}")
                sys.exit(1)
                
            with open(gamelist_path, 'r') as f:
                gamelist = json.load(f)
            
            # Search through all games for a title match
            all_games = []
            if gamelist.get('gameOfTheWeek') and gamelist['gameOfTheWeek'].get('id'):
                all_games.append(gamelist['gameOfTheWeek'])
            if gamelist.get('previousGames'):
                all_games.extend(gamelist['previousGames'])
            if gamelist.get('games'):
                all_games.extend(gamelist['games'])
            
            # Try exact match first
            for game in all_games:
                if game.get('title') == game_title:
                    return game.get('id')
            
            # Try case-insensitive match
            for game in all_games:
                if game.get('title', '').lower() == game_title.lower():
                    return game.get('id')
            
            # Try partial match
            for game in all_games:
                game_title_lower = game.get('title', '').lower()
                search_title_lower = game_title.lower()
                if search_title_lower in game_title_lower or game_title_lower in search_title_lower:
                    print(f"🔍 Found partial match: '{game.get('title')}' for '{game_title}'")
                    return game.get('id')
            
            print(f"❌ Error: No game found with title: {game_title}")
            sys.exit(1)
            
        except Exception as e:
            print(f"❌ Error: Error searching for game title: {e}")
            sys.exit(1)

    def read_game_metadata(self, game_id):
        """Read metadata from public/games/{gameid}/metadata.yaml."""
        meta_path = f'public/games/{game_id}/metadata.yaml'
        try:
            with open(meta_path, 'r') as f:
                meta = yaml.safe_load(f)
            return meta
        except FileNotFoundError:
            print(f"❌ Error: Could not find metadata file for game {game_id}: {meta_path}")
            sys.exit(1)
        except yaml.YAMLError as e:
            print(f"❌ Error: Invalid YAML in metadata file for game {game_id}: {e}")
            sys.exit(1)

    def generate_ai_prompt(self, game_title, meta):
        """Generate a prompt for the AI service to create an announcement message."""
        developer = meta.get('developer', 'Unknown')
        year = meta.get('year', 'Unknown')
        genre = meta.get('genre', 'Unknown')
        system = meta.get('system', 'Unknown')
        
        # Create a comprehensive prompt in French
        prompt = f"""Tu es un expert en jeux vidéo rétro qui écrit des annonces pour une newsletter hebdomadaire en français invitant les joueurs à tester ce jeu.

Voici les informations sur le jeu de la semaine :

Titre : {game_title}
Développeur : {developer}
Année : {year}
Genre : {genre}
Système : {system}

Ta tâche : Écrire une annonce en français qui décrit ce jeu de manière attrayante et engageante.

RÈGLES STRICTES :
- Maximum {MAX_SENTENCES} phrases complètes
- Ton enthousiaste et positif, adressé à la deuxième personne du pluriel.
- Décris pourquoi ce jeu est spécial ou amusant
- Mentionne un aspect unique ou intéressant
- Évite les clichés génériques
- Écris en français naturel et fluide

Exemples de bonnes annonces :
- "Découvrez H.E.R.O. (Helicopter Emergency Rescue Operation), un titre révolutionnaire d'Activision de 1984 qui a redéfini le genre action-aventure ! Dans ce jeu innovant, vous pilotez un hélicoptère équipé d'un jetpack pour sauver des mineurs piégés dans des cavernes souterraines. Combinez réflexes, stratégie et exploration pour naviguer à travers des labyrinthes complexes, éliminer des créatures hostiles et collecter des objets essentiels. Ce classique de l'Atari 2600 a marqué l'histoire du jeu vidéo avec sa mécanique unique et son gameplay addictif."
- "Plongez dans l'univers coloré de Balloon Fight, un classique Nintendo de 1985 qui a marqué l'ère NES ! Dans ce jeu d'action frénétique, vous incarnez un héros qui doit éclater des ballons flottants tout en évitant les ennemis volants. Utilisez votre hélicoptère personnel pour naviguer dans les airs, collectez des bonus et survivez le plus longtemps possible. Le jeu propose deux modes passionnants : le mode normal avec ses niveaux progressifs et le mode Balloon Trip, un mode survie sans fin où vous devez voler le plus loin possible en évitant les obstacles. Cette aventure aérienne légendaire a inspiré de nombreux jeux de plateforme à venir."
- "Préparez-vous pour Metal Slug 3, le chef-d'œuvre ultime de la série SNK sorti en 2000 ! Ce run 'n gun légendaire vous plonge dans une guerre épique contre une invasion extraterrestre, avec des graphismes 2D somptueux et des animations fluides qui ont défini l'âge d'or des jeux d'arcade. Incarnez Marco, Tarma, Eri ou Fio et utilisez un arsenal impressionnant d'armes, de véhicules et de power-ups pour éliminer hordes d'ennemis et boss gigantesques. Avec ses multiples chemins, ses transformations et son humour caractéristique, Metal Slug 3 reste l'un des plus grands jeux d'action de tous les temps !"


Génère maintenant l'annonce pour {game_title} :"""

        return prompt

    def call_openai_api(self, prompt):
        """Call OpenAI API to generate the announcement."""
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'model': 'gpt-4o-mini',  # Use GPT-4o-mini for cost efficiency
            'messages': [
                {'role': 'system', 'content': 'Tu es un expert en jeux vidéo rétro qui écrit des annonces en français.'},
                {'role': 'user', 'content': prompt}
            ],
            'max_tokens': 300,  # Increased to allow longer announcements
            'temperature': 0.8
        }
        
        try:
            response = requests.post(OPENAI_API_URL, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            announcement = result['choices'][0]['message']['content'].strip()
            
            # Clean up the response (remove quotes, extra formatting)
            announcement = re.sub(r'^["\']|["\']$', '', announcement)
            announcement = re.sub(r'\n+', ' ', announcement)
            
            return announcement
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error calling OpenAI API: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response: {e.response.text}")
            return None
        except Exception as e:
            print(f"❌ Error processing OpenAI response: {e}")
            return None

    def call_claude_api(self, prompt):
        """Call Anthropic Claude API to generate the announcement."""
        headers = {
            'x-api-key': self.api_key,
            'Content-Type': 'application/json',
            'anthropic-version': '2023-06-01'
        }
        
        data = {
            'model': 'claude-3-haiku-20240307',  # Use Haiku for cost efficiency
            'max_tokens': 300,  # Increased to allow longer announcements
            'messages': [
                {'role': 'user', 'content': prompt}
            ]
        }
        
        try:
            response = requests.post(ANTHROPIC_API_URL, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            announcement = result['content'][0]['text'].strip()
            
            # Clean up the response
            announcement = re.sub(r'^["\']|["\']$', '', announcement)
            announcement = re.sub(r'\n+', ' ', announcement)
            
            return announcement
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error calling Claude API: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response: {e.response.text}")
            return None
        except Exception as e:
            print(f"❌ Error processing Claude response: {e}")
            return None

    def generate_announcement(self, prompt):
        """Generate announcement using the selected AI service."""
        if self.ai_service == 'openai':
            return self.call_openai_api(prompt)
        elif self.ai_service == 'claude':
            return self.call_claude_api(prompt)
        else:
            print(f"❌ Error: Unsupported AI service: {self.ai_service}")
            return None

    def update_metadata_file(self, game_id, announcement):
        """Update the metadata.yaml file with the new announcement, preserving comments and exact values."""
        meta_path = f'public/games/{game_id}/metadata.yaml'
        
        try:
            # Read the file line by line to preserve comments and formatting
            with open(meta_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Find and update the announcement_message line
            updated = False
            for i, line in enumerate(lines):
                if line.strip().startswith('announcement_message:'):
                    # Preserve the exact indentation
                    indent = len(line) - len(line.lstrip())
                    lines[i] = ' ' * indent + f'announcement_message: "{announcement}"\n'
                    updated = True
                    break
            
            # If no existing announcement_message line found, add it at the end
            if not updated:
                # Find the last non-empty line to add the announcement
                last_line_index = len(lines) - 1
                while last_line_index >= 0 and not lines[last_line_index].strip():
                    last_line_index -= 1
                
                # Add a newline if the last line doesn't end with one
                if last_line_index >= 0 and not lines[last_line_index].endswith('\n'):
                    lines[last_line_index] += '\n'
                
                # Add the announcement message
                lines.append(f'announcement_message: "{announcement}"\n')
            
            # Write back to file, preserving all original content
            with open(meta_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            
            print(f"✅ Updated {meta_path} with new announcement message (preserved comments and formatting)")
            return True
            
        except Exception as e:
            print(f"❌ Error updating metadata file: {e}")
            return False

    def run(self, week_seed=None, next_week=False, update_metadata=False):
        """Run the announcement generation process."""
        print('🤖 Starting AI-powered announcement generation...')
        
        # Determine week seed
        if next_week:
            seed = self.get_next_week_seed()
            print(f"🎯 Using next week seed: {seed}")
        elif week_seed:
            seed = week_seed
            print(f"🎯 Using specified week seed: {seed}")
        else:
            seed = self.get_current_week_seed()
            print(f"🎯 Using current week seed: {seed}")
        
        # Get game information
        print("📖 Reading game of the week...")
        game_title = self.get_game_from_seed(seed)
        game_id = self.find_game_id_by_title(game_title)
        print(f'✅ Game of the week: {game_id} ({game_title})')
        
        # Read metadata
        print("📖 Reading game metadata...")
        meta = self.read_game_metadata(game_id)
        print('✅ Metadata loaded')
        
        # Check if announcement already exists
        existing_announcement = meta.get('announcement_message', '') or ''
        if existing_announcement.strip():
            print(f"📝 Existing announcement found: {existing_announcement}")
            response = input("Do you want to replace it? (y/N): ").strip().lower()
            if response not in ['y', 'yes']:
                print("🛑 Keeping existing announcement. Exiting.")
                return
        
        # Generate AI prompt
        print("✍️  Generating AI prompt...")
        prompt = self.generate_ai_prompt(game_title, meta)
        
        if self.dry_run:
            print("\n=== DRY RUN MODE ===")
            print("Prompt that would be sent to AI:")
            print("-" * 50)
            print(prompt)
            print("-" * 50)
            print("Would generate announcement using:", self.ai_service.upper())
            return
        
        # Call AI API
        print(f"🤖 Calling {self.ai_service.upper()} API...")
        announcement = self.generate_announcement(prompt)
        
        if not announcement:
            print("❌ Failed to generate announcement")
            sys.exit(1)
        
        # Validate sentence count with smarter parsing
        # Use a more sophisticated approach to count actual sentences
        import re
        
        # First, normalize the text to handle common abbreviation patterns
        normalized_text = announcement
        
        # Handle common abbreviation patterns (H.E.R.O., U.S.A., etc.)
        # Replace periods in acronyms with a temporary marker
        normalized_text = re.sub(r'\b([A-Z]\.){2,}', lambda m: m.group(0).replace('.', '§'), normalized_text)
        
        # Handle other common abbreviations (Mr., Dr., etc.)
        normalized_text = re.sub(r'\b([A-Z][a-z]\.)', lambda m: m.group(0).replace('.', '§'), normalized_text)
        
        # Now split by periods to get sentences
        raw_parts = normalized_text.split('.')
        sentences = []
        
        for part in raw_parts:
            part = part.strip()
            if not part:
                continue
            
            # Restore periods in abbreviations
            part = part.replace('§', '.')
            
            # Check if this looks like a complete sentence
            if len(part) > 10 and not part.isupper():  # Must be substantial and not just an acronym
                sentences.append(part)
            elif len(part) <= 10 and part.isupper():
                # This is likely an acronym, skip it as a separate sentence
                continue
            elif len(part) > 10:
                # This might be a sentence, include it
                sentences.append(part)
        
        sentence_count = len(sentences)
        
        if sentence_count > MAX_SENTENCES:
            print(f"⚠️  Warning: Generated announcement has {sentence_count} sentences (max {MAX_SENTENCES})")
            print("Truncating to fit...")
            # Keep only the first MAX_SENTENCES sentences
            truncated_sentences = sentences[:MAX_SENTENCES]
            announcement = '. '.join(truncated_sentences) + '.'
            print(f"✅ Truncated to {MAX_SENTENCES} sentences")
        
        print(f"✅ Generated announcement ({sentence_count} sentences, {len(announcement)} characters):")
        print(f"📝 {announcement}")
        
        # Update metadata file if requested
        if update_metadata:
            print("💾 Updating metadata file...")
            if self.update_metadata_file(game_id, announcement):
                print("🎉 Announcement successfully added to metadata!")
            else:
                print("❌ Failed to update metadata file")
        else:
            print("\n💡 To automatically update the metadata file, run with --update-metadata")
            print(f"💡 Or manually add this line to public/games/{game_id}/metadata.yaml:")
            print(f"   announcement_message: \"{announcement}\"")

def main():
    parser = argparse.ArgumentParser(description='Generate AI-powered announcement messages for BonjourArcade games')
    parser.add_argument('--week-seed', default=None, type=str,
                       help='Specific week seed (YYYYWW format) to use instead of current week')
    parser.add_argument('--next-week', action='store_true',
                       help='Use next week\'s seed instead of current week (useful when you don\'t know the current week number)')
    parser.add_argument('--ai-service', default=DEFAULT_AI_SERVICE, choices=['openai', 'claude'],
                       help='AI service to use (default: openai)')
    parser.add_argument('--update-metadata', action='store_true',
                       help='Automatically update the metadata.yaml file with the generated announcement')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be generated without actually calling AI or updating files')
    
    args = parser.parse_args()
    
    # Validate that --week-seed and --next-week are not both specified
    if args.week_seed and args.next_week:
        print('❌ Error: Cannot specify both --week-seed and --next-week. Use one or the other.')
        sys.exit(1)
    
    # Validate AI service and API keys (only if not in dry-run mode)
    if not args.dry_run:
        if args.ai_service == 'openai' and not os.getenv('OPENAI_API_KEY'):
            print('❌ Error: OPENAI_API_KEY environment variable is required for OpenAI service.')
            print('   Set it with: export OPENAI_API_KEY="your-api-key-here"')
            sys.exit(1)
        elif args.ai_service == 'claude' and not os.getenv('ANTHROPIC_API_KEY'):
            print('❌ Error: ANTHROPIC_API_KEY environment variable is required for Claude service.')
            print('   Set it with: export ANTHROPIC_API_KEY="your-api-key-here"')
            sys.exit(1)
    
    generator = AnnouncementGenerator(
        ai_service=args.ai_service,
        dry_run=args.dry_run
    )
    
    generator.run(
        week_seed=args.week_seed,
        next_week=args.next_week,
        update_metadata=args.update_metadata
    )

if __name__ == '__main__':
    main()
