"""
Adaptation Engine for Adaptive Museum Explorer
Applies context-aware rules to modify UI behavior based on user profile and environmental context
"""

from flask import session


def get_active_settings(user_profile=None, context=None):
    """
    Get active adaptation settings based on user profile and context
    
    Args:
        user_profile (dict, optional): User profile data from database
        context (dict, optional): Current session context (device, connection, time, etc.)
        
    Returns:
        dict: Active settings dictionary with adaptation rules applied
    """
    # Default settings (baseline)
    settings = {
        'show_images': True,
        'max_results': 12,
        'description_length': 'full',
        'layout': 'grid',
        'adaptation_reasons': []  # For transparency log
    }
    
    # Initialize context if not provided (for testing/demo)
    if context is None:
        context = {
            'connection_quality': 'good',  # 'good', 'poor'
            'time_available': 60,  # minutes
            'device': 'desktop'  # 'desktop', 'mobile', 'tablet'
        }
    
    # Rule 1: Bandwidth Rule
    # If connection quality is poor, hide images to reduce data usage
    if context.get('connection_quality') == 'poor':
        settings['show_images'] = False
        settings['adaptation_reasons'].append('connection is poor')
    
    # Rule 2: Time Constraint Rule
    # If user has limited time (<= 15 minutes), show fewer results and shorter descriptions
    time_available = context.get('time_available', 60)
    if time_available <= 15:
        settings['max_results'] = 3
        settings['description_length'] = 'short'
        settings['adaptation_reasons'].append(f'you have {time_available} minutes')
    
    # Rule 3: Mobile Context Rule
    # If device is mobile, use list layout only (same number of museums as desktop)
    if context.get('device') == 'mobile':
        settings['layout'] = 'list'
        if 'mobile device' not in [r for r in settings['adaptation_reasons']]:
            settings['adaptation_reasons'].append('mobile device')
    
    return settings


def get_adaptation_log_message(settings):
    """
    Generate a human-readable adaptation log message for transparency
    
    Args:
        settings (dict): Active settings dictionary
        
    Returns:
        str: Adaptation log message
    """
    if not settings.get('adaptation_reasons'):
        return None  # Don't show log if no adaptations
    
    reasons = settings['adaptation_reasons']
    
    # Build the message
    adaptations = []
    
    if not settings.get('show_images'):
        adaptations.append("hiding images")
    
    if settings.get('description_length') == 'short':
        adaptations.append("shortening descriptions")
    
    if settings.get('max_results') < 12:
        adaptations.append(f"showing {settings['max_results']} results")
    
    if settings.get('layout') == 'list':
        adaptations.append("using list layout")
    
    adaptation_text = " and ".join(adaptations) if adaptations else "applying optimizations"
    reason_text = " and ".join(reasons)
    
    return f"System adapted: {adaptation_text.capitalize()} because {reason_text}."


def detect_context(request):
    """
    Detect current context from Flask request
    
    Args:
        request: Flask request object
        
    Returns:
        dict: Detected context (device, connection quality, etc.)
    """
    # Start with defaults and optionally override time with session value
    context = {
        'device': 'desktop',
        'connection_quality': 'good',
        'time_available': session.get('time_available_minutes', 60)  # Default to 60 minutes
    }
    
    # Detect device from user agent
    user_agent = request.headers.get('User-Agent', '').lower()
    if 'mobile' in user_agent or 'android' in user_agent or 'iphone' in user_agent:
        context['device'] = 'mobile'
    elif 'tablet' in user_agent or 'ipad' in user_agent:
        context['device'] = 'tablet'
    
    # Get connection quality from session (can be set by frontend)
    # For now, we'll use a simple detection or default to 'good'
    # In production, this could come from navigator.connection API
    connection_quality = request.args.get('connection_quality') or 'good'
    context['connection_quality'] = connection_quality
    
    # Get time available from session or query parameter
    time_available = request.args.get('time_available')
    if time_available:
        try:
            context['time_available'] = int(time_available)
        except ValueError:
            pass
    
    return context
