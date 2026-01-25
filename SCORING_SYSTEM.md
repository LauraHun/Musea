# Dynamic User Profile Scoring System

## Overview

The scoring system processes interaction tracking data to build dynamic user profiles with theme affinities and museum popularity scores.

## Scoring Weights

As defined in the project report:

- **Click**: +1 point (clicking on a museum card)
- **Detail Open**: +2 points (opening the detail page)
- **Favorite**: +3 points (clicking the favorite button)
- **Reading Time**: +1 point per 30 seconds spent reading (capped at 10 minutes to avoid outliers)

## Files

### `scoring.py`
Contains all the scoring logic functions:

- `process_interaction()` - Main function to process an interaction
- `update_theme_affinity()` - Updates user's theme scores
- `update_museum_popularity()` - Updates global museum popularity
- `update_engagement_score()` - Tracks total session engagement
- `get_user_profile()` - Retrieves complete user profile
- `get_museum_stats()` - Gets museum popularity statistics

### `app.py`
The `/track_interaction` route now automatically processes interactions through the scoring system.

## How It Works

1. **JavaScript sends interaction data** → `/track_interaction` endpoint
2. **Flask route extracts data** → `museum_id`, `interaction_type`, `duration_sec`
3. **Scoring system processes interaction**:
   - Calculates points based on interaction type
   - Identifies museum theme
   - Updates theme affinity for the user
   - Updates global museum popularity
   - Updates session engagement score
4. **Results logged to console** for verification

## Testing

### Test the Scoring Logic

Run the standalone test:
```bash
python scoring.py
```

This will show:
- Points calculation for different interaction types
- Theme affinity updates
- Museum popularity updates
- Engagement score accumulation

### Test in Flask App

1. Start Flask: `python app.py`
2. Navigate to museum gallery
3. Interact with museums (click, favorite, read)
4. Watch the Flask console for scoring results:
   ```
   Logged click for museum 1
     📊 SCORING RESULTS:
        Points Earned: 1
        Theme: Art
        Theme Score: 1
        Museum Popularity: 1
        Total Engagement: 1
   ```

### View User Profile

Visit: `http://localhost:5000/user_profile`

This shows:
- Total engagement score
- Theme affinities (all themes with scores)
- Top 3 themes
- Most popular museums (global)

## Example Output

### Console Output (Flask)
```
Logged click for museum 1
  Timestamp: 2026-01-24T10:30:45.123Z

  📊 SCORING RESULTS:
     Points Earned: 1
     Theme: Art
     Theme Score: 1
     Museum Popularity: 1
     Total Engagement: 1

Logged reading for museum 1 - Duration: 90 seconds
  Timestamp: 2026-01-24T10:31:00.456Z
  Duration: 90 seconds

  📊 SCORING RESULTS:
     Points Earned: 5
     Theme: Art
     Theme Score: 6
     Museum Popularity: 6
     Total Engagement: 6

Logged favorite for museum 6 - State: added
  Timestamp: 2026-01-24T10:32:00.789Z

  📊 SCORING RESULTS:
     Points Earned: 3
     Theme: Science
     Theme Score: 3
     Museum Popularity: 3
     Total Engagement: 9
```

## Mock Database Structure

Currently using in-memory dictionaries (will be replaced with SQLite):

```python
mock_db = {
    'theme_affinity': {
        'user_id': {
            'Art': 6,
            'Science': 3,
            'History': 1
        }
    },
    'museum_popularity': {
        'museum_id': popularity_score
    },
    'session_engagement': {
        'user_id': total_engagement_score
    }
}
```

## Integration with Real Database

When your teammate creates the SQLite tables, replace the mock dictionary operations with:

1. **Theme Affinity Table**: `theme_stats(user_id, theme, score)`
2. **Museum Popularity Table**: `museum_popularity(museum_id, popularity_score)`
3. **User Engagement Table**: `user_engagement(user_id, engagement_score)`

Update functions in `scoring.py` to use `get_db()` and SQL queries instead of `mock_db`.

## Functions Reference

### `process_interaction(user_id, museum_id, interaction_type, duration_sec=None)`
Main processing function. Returns a dictionary with all updates.

### `get_user_profile(user_id)`
Returns complete user profile with theme affinities, top themes, and engagement score.

### `get_museum_stats(museum_id)`
Returns museum popularity score and theme.

### `calculate_interaction_points(interaction_type, duration_sec=None)`
Calculates points for a specific interaction type.

### `calculate_reading_points(duration_sec)`
Calculates points from reading time (+1 per 30 seconds, capped).

## Notes

- Reading time is capped at 600 seconds (10 minutes) to avoid outliers
- Points are only added for valid interactions (positive points)
- Theme identification uses the `MUSEUM_THEMES` dictionary (will come from database later)
- All scoring happens automatically when interactions are tracked
