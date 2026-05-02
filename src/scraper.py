
"""
BBC Football Scores Scraper - Fixed Version
Fetches live scores, fixtures, and results from BBC Sport
Supports 3-day fetching: Today, Tomorrow, and After Tomorrow
"""

import json
import re
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pytz


class BBCFootballScraper:
    """Scraper for BBC Football Scores and Fixtures using JSON extraction"""

    BASE_URL = "https://www.bbc.com/sport/football/scores-fixtures"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
        self.egypt_tz = pytz.timezone('Africa/Cairo')

    def get_team_logo(self, team_name: str) -> str:
        """Generate team logo URL (fallback service)"""
        team_slug = team_name.lower().replace(' ', '-').replace('.', '').replace("'", "")
        return f"https://ssl.gstatic.com/onebox/media/sports/logos/{team_slug}_64x64.png"

    def convert_to_egypt_time(self, iso_date_str: str) -> str:
        """Convert UTC ISO date to Egypt time (HH:MM)"""
        try:
            # BBC uses UTC (Z)
            utc_dt = datetime.fromisoformat(iso_date_str.replace('Z', '+00:00'))
            egypt_dt = utc_dt.astimezone(self.egypt_tz)
            return egypt_dt.strftime("%H:%M")
        except Exception:
            return "N/A"

    def fetch_day_scores(self, date: datetime) -> List[Dict]:
        """Fetch scores for a specific date by extracting JSON from BBC page"""
        try:
            date_str = date.strftime("%Y-%m-%d")
            url = f"{self.BASE_URL}/{date_str}"
            
            response = self.session.get(url, timeout=20)
            response.raise_for_status()
            html = response.text
            
            # Extract window.__INITIAL_DATA__
            match = re.search(r'window\.__INITIAL_DATA__\s*=\s*"(.*?)";', html, re.DOTALL)
            if not match:
                return []
            
            # Unescape and parse JSON
            data_str = json.loads(f'"{match.group(1)}"')
            full_data = json.loads(data_str)
            
            # Find the scores-fixtures data block
            leagues_data = []
            for key, value in full_data.get('data', {}).items():
                if 'sport-data-scores-fixtures' in key:
                    event_groups = value.get('data', {}).get('eventGroups', [])
                    for group in event_groups:
                        league_name = group.get('displayLabel', 'Unknown League')
                        matches = []
                        
                        # BBC nests matches in secondaryGroups
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
        
        # Status and Time
        status_comment = event.get('statusComment', {}).get('value', '')
        period_label = event.get('periodLabel', {}).get('value', '')
        
        # Determine status
        is_full_time = status_comment == 'FT' or period_label == 'FT'
        is_live = event.get('status') == 'MidEvent'
        is_upcoming = event.get('status') == 'PreEvent'
        
        # Display time/minute
        display_time = status_comment if status_comment else event.get('date', {}).get('time', '')
        
        # Scores
        home_score = home.get('score')
        away_score = away.get('score')
        
        return {
            "home_team": {
                "name": home_name,
                "logo_url": self.get_team_logo(home_name)
            },
            "away_team": {
                "name": away_name,
                "logo_url": self.get_team_logo(away_name)
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

    # Save to JSON
    with open('football_scores.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # Print summary
    print(f"Fetch completed at {result['egypt_time']}")
    for day in result['days']:
        match_total = sum(l['match_count'] for l in day['leagues'])
        print(f"- {day['label']}: Found {len(day['leagues'])} leagues, {match_total} matches")


if __name__ == "__main__":
    main()
