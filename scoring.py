"""
Dynamic User Profile Scoring System
Processes interaction tracking data to build user interest scores and museum popularity
"""

"""
NOTE:
This module is now focused on *stateless* scoring:
- `calculate_interaction_points` computes the number of points for an interaction.
- `process_interaction` returns a structured summary of the scoring result.

All persistent storage of theme affinities, museum popularity and engagement
is handled by the database layer in `db_manager.py`. Any previous in‑memory
mock structures (mock_db, MUSEUM_THEMES, etc.) have been removed.
"""

# Scoring weights as defined in project report
SCORING_WEIGHTS = {
    'click': 1,           # Click on museum card
    'reading': 2,         # Detail page opened (initial)
    'favorite': 3,        # Favorite button clicked
    'reading_time': 1,    # Per 30 seconds of reading (capped)
    # Explicit feedback – used by /feedback route
    'thumbs_up': 3,
    'thumbs_down': 1,
}

# Reading time cap (in seconds) to avoid outliers
MAX_READING_TIME_SEC = 600  # 10 minutes cap


def calculate_reading_points(duration_sec):
    """
    Calculate points from reading time: +1 point per 30 seconds (capped)
    
    Args:
        duration_sec (int): Reading duration in seconds
        
    Returns:
        int: Points earned from reading time
    """
    if not duration_sec or duration_sec <= 0:
        return 0
    
    # Cap the duration to avoid outliers
    capped_duration = min(duration_sec, MAX_READING_TIME_SEC)
    
    # Calculate points: +1 per 30 seconds
    points = capped_duration // 30
    
    return points


def calculate_interaction_points(interaction_type, duration_sec=None):
    """
    Calculate points for a given interaction type
    
    Args:
        interaction_type (str): Type of interaction ('click', 'reading', 'favorite')
        duration_sec (int, optional): Reading duration for 'reading' type
        
    Returns:
        int: Points earned from this interaction
    """
    if interaction_type in ('click', 'view-details'):
        return SCORING_WEIGHTS['click']
    
    elif interaction_type == 'reading':
        # Initial detail page open: +2 points
        base_points = SCORING_WEIGHTS['reading']
        
        # Additional points from reading time: +1 per 30 seconds
        reading_points = calculate_reading_points(duration_sec) if duration_sec else 0
        
        return base_points + reading_points
    
    elif interaction_type == 'favorite':
        return SCORING_WEIGHTS['favorite']
    
    elif interaction_type == 'thumbs_up':
        # Treat an explicit thumbs up similarly to a "strong positive" signal
        return SCORING_WEIGHTS['thumbs_up']
    
    elif interaction_type == 'thumbs_down':
        # Still counts toward engagement, but with lower weight
        return SCORING_WEIGHTS['thumbs_down']
    
    else:
        return 0


def process_interaction(user_id, museum_id, interaction_type, duration_sec=None, theme=None):
    """
    Main function to process an interaction and update all relevant scores
    
    Args:
        user_id (str): User identifier
        museum_id (str): Museum identifier
        interaction_type (str): Type of interaction ('click', 'view-details', 'reading', 'favorite')
        duration_sec (int, optional): Reading duration for 'reading' type
        theme (str, optional): Museum theme from DB; if provided, used instead of get_museum_theme(museum_id)
        
    Returns:
        dict: Summary of all updates made
    """
    # Calculate points for this interaction
    points = calculate_interaction_points(interaction_type, duration_sec)
    
    if points <= 0:
        return {
            'status': 'no_points',
            'message': 'No points calculated for this interaction'
        }
    
    # Normalise theme string if provided; persistent updates are done in db_manager.
    if isinstance(theme, str):
        theme = theme.strip() or None

    result = {
        'user_id': user_id,
        'museum_id': museum_id,
        'interaction_type': interaction_type,
        'points_earned': points,
        'theme': theme,
        'updates': {}
    }
    
    # For phase 1, we keep this function side‑effect free. The DB layer is responsible
    # for persisting scores; callers can optionally inspect this summary object.
    return result
