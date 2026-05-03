
"""
BBC Football Scores Scraper - Final Fixed Version 4.1
Fetches live scores, fixtures, and results from BBC Sport
Supports 3-day fetching: Today, Tomorrow, and After Tomorrow
Fixed: Dynamic SVG team logos extracted directly from page assets
Updated: Added league exclusion list to filter out unwanted competitions
"""

import json
import re
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pytz


class BBCFootballScraper:
    """Scraper for BBC Football Scores and Fixtures with dynamic SVG logo extraction"""

    BASE_URL = "https://www.bbc.com/sport/football/scores-fixtures"

    # List of leagues/competitions to exclude from the final output
    EXCLUDED_LEAGUES = [
        "Scottish", "Women's", "Irish", "Austrian", "Brazilian", "Croatia",
        "Danish", "Chinese", "Dutch", "Finnish", "Indian", "Nigerian",
        "Norwegian", "Polish", "Serbian", "Swedish", "Ukraine", "Belgian",
        "South Africa", "Australian", "Czech", "Greek", "Swiss"
    ]

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        })
        self.egypt_tz = pytz.timezone('Africa/Cairo')
        self.logo_map = {}

    def build_logo_map(self, html: str):
        """
        Extract all SVG logo links from the HTML content.
        BBC logos follow the pattern: .../football/team-name.hash.svg
        """
        # Regex to find BBC football SVG logos
        pattern = r'https?://static\.files\.bbci\.co\.uk/[^\s"\'<>]*?/sport/football/([a-z0-9\-]+)\.[a-z0-9]+\.svg'
        matches = re.findall(pattern, html)
        links = re.findall(r'https?://static\.files\.bbci\.co\.uk/[^\s"\'<>]*?/sport/football/[a-z0-9\-]+\.[a-z0-9]+\.svg', html)
        
        for name_slug, link in zip(matches, links):
            self.logo_map[name_slug] = link
            
        print(f"Built logo map with {len(self.logo_map)} unique team logos.")

    def get_dynamic_logo(self, team_name: str, team_urn: str) -> str:
        """Get the dynamic SVG logo from the map using team name or URN slug"""
        urn_slug = team_urn.split(':')[-1] if team_urn else ""
        if urn_slug in self.logo_map:
            return self.logo_map[urn_slug]
            
        name_slug = team_name.lower().replace(' ', '-').replace('.', '').replace("'", "")
        if name_slug in self.logo_map:
            return self.logo_map[name_slug]
            
        return f"https://ssl.gstatic.com/onebox/media/sports/logos/{name_slug}_64x64.png"

    def convert_to_egypt_time(self, iso_date_str: str) -> str:
        """Convert UTC ISO date to Egypt time (HH:MM)"""
        try:
            utc_dt = datetime.fromisoformat(iso_date_str.replace('Z', '+00:00'))
            egypt_dt = utc_dt.astimezone(self.egypt_tz)
            return egypt_dt.strftime("%H:%M")
        except Exception:
            return "N/A"

    def is_excluded(self, league_name: str) -> bool:
        """Check if the league name contains any of the excluded keywords"""
        for excluded in self.EXCLUDED_LEAGUES:
            if excluded.lower() in league_name.lower():
                return True
        return False

    def fetch_day_scores(self, date: datetime) -> List[Dict]:
        """Fetch scores for a specific date by extracting JSON and Assets from BBC page"""
        try:
            date_str = date.strftime("%Y-%m-%d")
            url = f"{self.BASE_URL}/{date_str}"
            
            response = self.session.get(url, timeout=20)
            response.raise_for_status()
            html = response.text
            
            self.build_logo_map(html)
            
            match = re.search(r'window\.__INITIAL_DATA__\s*=\s*"(.*?)";', html, re.DOTALL)
            if not match:
                return []
            
            data_str = json.loads(f'"{match.group(1)}"')
            full_data = json.loads(data_str)
            
            leagues_data = []
            for key, value in full_data.get('data', {}).items():
                if 'sport-data-scores-fixtures' in key:
                    event_groups = value.get('data', {}).get('eventGroups', [])
                    for group in event_groups:
                        league_name = group.get('displayLabel', 'Unknown League')
                        
                        # Skip excluded leagues
                        if self.is_excluded(league_name):
                            continue
                            
                        matches = []
                        for sec_group in group.get('secondaryGroups', []):
                            for event in sec_group.get('events', []):
                                matches.append(self.parse_event(event))
                        
                        if matches:
                            leagues_data.append({
                                "name": league_name,
                                "match_count": len(matches),
                                "matches": matches
                            })
            return leagues_data
            
        except Exception as e:
            print(f"Error fetching for {date.strftime('%Y-%m-%d')}: {e}")
            return []

    def parse_event(self, event: Dict) -> Dict:
        """Parse a single match event from BBC JSON structure"""
        home = event.get('home', {})
        away = event.get('away', {})
        
        home_name = home.get('fullName', 'TBD')
        away_name = away.get('fullName', 'TBD')
        
        home_logo = self.get_dynamic_logo(home_name, home.get('urn', ''))
        away_logo = self.get_dynamic_logo(away_name, away.get('urn', ''))
        
        status_comment = event.get('statusComment', {}).get('value', '')
        period_label = event.get('periodLabel', {}).get('value', '')
        
        is_full_time = status_comment == 'FT' or period_label == 'FT'
        is_live = event.get('status') == 'MidEvent'
        is_upcoming = event.get('status') == 'PreEvent'
        
        display_time = status_comment if status_comment else event.get('date', {}).get('time', '')
        
        home_score = home.get('score')
        away_score = away.get('score')
        
        return {
            "home_team": {
                "name": home_name,
                "logo_url": home_logo
            },
            "away_team": {
                "name": away_name,
                "logo_url": away_logo
            },
            "score": {
                "home": home_score,
                "away": away_score,
                "display": f"{home_score} - {away_score}" if home_score is not None else "vs"
            },
            "time": {
                "display": display_time,
                "egypt": self.convert_to_egypt_time(event.get('startDateTime', '')),
                "status": event.get('status'),
                "is_live": is_live,
                "is_full_time": is_full_time,
                "is_upcoming": is_upcoming
            }
        }

    def fetch_scores(self) -> Dict:
        """Main method to fetch and parse football scores for 3 days"""
        result = {
            "timestamp": datetime.now(pytz.UTC).isoformat(),
            "egypt_time": datetime.now(self.egypt_tz).strftime("%Y-%m-%d %H:%M:%S"),
            "source": "BBC Sport",
            "source_url": self.BASE_URL,
            "days": []
        }

        today = datetime.now(self.egypt_tz).date()

        for day_offset in range(3):
            current_date = today + timedelta(days=day_offset)
            
            if day_offset == 0:
                day_label = f"Today({current_date.strftime('%d-%m-%Y')})"
            elif day_offset == 1:
                day_label = f"Tomorrow({current_date.strftime('%d-%m-%Y')})"
            else:
                day_label = f"After Tomorrow({current_date.strftime('%d-%m-%Y')})"

            leagues = self.fetch_day_scores(current_date)

            result["days"].append({
                "label": day_label,
                "date": current_date.isoformat(),
                "day_offset": day_offset,
                "leagues": leagues
            })

        return result


def main():
    """Main execution"""
    scraper = BBCFootballScraper()
    result = scraper.fetch_scores()

    with open('football_scores.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Fetch completed at {result['egypt_time']}")
    for day in result['days']:
        match_total = sum(l['match_count'] for l in day['leagues'])
        print(f"- {day['label']}: Found {len(day['leagues'])} leagues, {match_total} matches")


if __name__ == "__main__":
    main()
