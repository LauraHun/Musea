"""
Dynamic User Profile Scoring System
Processes interaction tracking data to build user interest scores and museum popularity
"""

# Mock database storage (will be replaced with SQLite tables later)
mock_db = {
    'theme_affinity': {},  # {user_id: {theme: score}}
    'museum_popularity': {},  # {museum_id: popularity_score}
    'session_engagement': {}  # {user_id: engagement_score}
}

# Museum theme lookup (temporary - will come from database)
MUSEUM_THEMES = {
    '1': 'Art',
    '2': 'Art',
    '3': 'History',
    '4': 'Art',
    '5': 'Art',
    '6': 'Science',
    '7': 'Local Heritage',
    '8': 'Art',
    '9': 'Science',
    '10': 'Local Heritage',
    '11': 'Art',
    '12': 'Science'
}

# Scoring weights as defined in project report
SCORING_WEIGHTS = {
    'click': 1,          # Click on museum card
    'reading': 2,        # Detail page opened (initial)
    'favorite': 3,        # Favorite button clicked
    'reading_time': 1    # Per 30 seconds of reading (capped)
}

# Reading time cap (in seconds) to avoid outliers
MAX_READING_TIME_SEC = 600  # 10 minutes cap


def get_museum_theme(museum_id):
    """
    Get the theme of a museum by its ID
    
    Args:
        museum_id (str): Museum identifier
        
    Returns:
        str: Theme name (e.g., 'Art', 'Science', 'History') or None
    """
    return MUSEUM_THEMES.get(str(museum_id))


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
    if interaction_type == 'click':
        return SCORING_WEIGHTS['click']
    
    elif interaction_type == 'reading':
        # Initial detail page open: +2 points
        base_points = SCORING_WEIGHTS['reading']
        
        # Additional points from reading time: +1 per 30 seconds
        reading_points = calculate_reading_points(duration_sec) if duration_sec else 0
        
        return base_points + reading_points
    
    elif interaction_type == 'favorite':
        return SCORING_WEIGHTS['favorite']
    
    else:
        return 0


def update_theme_affinity(user_id, theme, points):
    """
    Update the theme affinity score for a user
    
    Args:
        user_id (str): User identifier
        theme (str): Theme name (e.g., 'Art', 'Science')
        points (int): Points to add to the theme score
        
    Returns:
        dict: Updated theme affinity scores for the user
    """
    if not user_id or not theme or points <= 0:
        return mock_db['theme_affinity'].get(user_id, {})
    
    # Initialize user's theme scores if not exists
    if user_id not in mock_db['theme_affinity']:
        mock_db['theme_affinity'][user_id] = {}
    
    # Update or initialize theme score
    if theme in mock_db['theme_affinity'][user_id]:
        mock_db['theme_affinity'][user_id][theme] += points
    else:
        mock_db['theme_affinity'][user_id][theme] = points
    
    return mock_db['theme_affinity'][user_id]


def update_museum_popularity(museum_id, points):
    """
    Update the global popularity score for a museum
    
    Args:
        museum_id (str): Museum identifier
        points (int): Points to add to the popularity score
        
    Returns:
        int: Updated popularity score for the museum
    """
    if not museum_id or points <= 0:
        return mock_db['museum_popularity'].get(museum_id, 0)
    
    # Initialize museum popularity if not exists
    if museum_id not in mock_db['museum_popularity']:
        mock_db['museum_popularity'][museum_id] = 0
    
    # Update popularity score
    mock_db['museum_popularity'][museum_id] += points
    
    return mock_db['museum_popularity'][museum_id]


def update_engagement_score(user_id, points):
    """
    Update the total engagement score for the current session
    
    Args:
        user_id (str): User identifier
        points (int): Points to add to engagement score
        
    Returns:
        int: Updated total engagement score
    """
    if not user_id or points <= 0:
        return mock_db['session_engagement'].get(user_id, 0)
    
    # Initialize engagement score if not exists
    if user_id not in mock_db['session_engagement']:
        mock_db['session_engagement'][user_id] = 0
    
    # Update engagement score
    mock_db['session_engagement'][user_id] += points
    
    return mock_db['session_engagement'][user_id]


def process_interaction(user_id, museum_id, interaction_type, duration_sec=None):
    """
    Main function to process an interaction and update all relevant scores
    
    Args:
        user_id (str): User identifier
        museum_id (str): Museum identifier
        interaction_type (str): Type of interaction ('click', 'reading', 'favorite')
        duration_sec (int, optional): Reading duration for 'reading' type
        
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
    
    # Get museum theme
    theme = get_museum_theme(museum_id)
    
    result = {
        'user_id': user_id,
        'museum_id': museum_id,
        'interaction_type': interaction_type,
        'points_earned': points,
        'theme': theme,
        'updates': {}
    }
    
    # Update theme affinity (if theme exists)
    if theme:
        updated_themes = update_theme_affinity(user_id, theme, points)
        result['updates']['theme_affinity'] = updated_themes
        result['updates']['theme_score'] = updated_themes.get(theme, 0)
    else:
        result['updates']['theme_affinity'] = 'Theme not found'
    
    # Update museum popularity
    updated_popularity = update_museum_popularity(museum_id, points)
    result['updates']['museum_popularity'] = updated_popularity
    
    # Update engagement score
    updated_engagement = update_engagement_score(user_id, points)
    result['updates']['engagement_score'] = updated_engagement
    
    return result


def get_user_profile(user_id):
    """
    Get the complete dynamic profile for a user
    
    Args:
        user_id (str): User identifier
        
    Returns:
        dict: User's theme affinities, engagement score, and top themes
    """
    theme_scores = mock_db['theme_affinity'].get(user_id, {})
    engagement = mock_db['session_engagement'].get(user_id, 0)
    
    # Sort themes by score (descending)
    sorted_themes = sorted(
        theme_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )
    
    return {
        'user_id': user_id,
        'theme_affinities': theme_scores,
        'top_themes': sorted_themes[:3] if sorted_themes else [],
        'engagement_score': engagement,
        'total_themes': len(theme_scores)
    }


def get_museum_stats(museum_id):
    """
    Get popularity statistics for a museum
    
    Args:
        museum_id (str): Museum identifier
        
    Returns:
        dict: Museum popularity score and theme
    """
    return {
        'museum_id': museum_id,
        'popularity_score': mock_db['museum_popularity'].get(museum_id, 0),
        'theme': get_museum_theme(museum_id)
    }


def reset_mock_db():
    """Reset all mock database data (for testing)"""
    global mock_db
    mock_db = {
        'theme_affinity': {},
        'museum_popularity': {},
        'session_engagement': {}
    }


# Example usage and testing
if __name__ == '__main__':
    print("=" * 60)
    print("Testing Dynamic User Profile Scoring System")
    print("=" * 60)
    
    # Reset for clean test
    reset_mock_db()
    
    user_id = 'demo_user_1'
    
    print("\n1. User clicks on museum card (Art theme):")
    result = process_interaction(user_id, '1', 'click')
    print(f"   Points: {result['points_earned']}")
    print(f"   Theme Score (Art): {result['updates']['theme_score']}")
    print(f"   Museum Popularity: {result['updates']['museum_popularity']}")
    print(f"   Engagement Score: {result['updates']['engagement_score']}")
    
    print("\n2. User opens detail page and reads for 90 seconds:")
    result = process_interaction(user_id, '1', 'reading', duration_sec=90)
    print(f"   Points: {result['points_earned']} (2 base + 3 for 90s reading)")
    print(f"   Theme Score (Art): {result['updates']['theme_score']}")
    print(f"   Engagement Score: {result['updates']['engagement_score']}")
    
    print("\n3. User favorites a Science museum:")
    result = process_interaction(user_id, '6', 'favorite')
    print(f"   Points: {result['points_earned']}")
    print(f"   Theme Score (Science): {result['updates']['theme_score']}")
    print(f"   Engagement Score: {result['updates']['engagement_score']}")
    
    print("\n4. User clicks on History museum:")
    result = process_interaction(user_id, '3', 'click')
    print(f"   Points: {result['points_earned']}")
    print(f"   Theme Score (History): {result['updates']['theme_score']}")
    
    print("\n5. Complete User Profile:")
    profile = get_user_profile(user_id)
    print(f"   Engagement Score: {profile['engagement_score']}")
    print(f"   Theme Affinities: {profile['theme_affinities']}")
    print(f"   Top Themes: {profile['top_themes']}")
    
    print("\n6. Museum Popularity Stats:")
    for museum_id in ['1', '3', '6']:
        stats = get_museum_stats(museum_id)
        print(f"   Museum {museum_id} ({stats['theme']}): {stats['popularity_score']} points")
    
    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)
