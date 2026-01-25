from flask import Flask, render_template, request, redirect, url_for, session, g
import sqlite3
import os
from functools import wraps
from scoring import process_interaction, get_user_profile, get_museum_stats
from adaptation import get_active_settings, get_adaptation_log_message, detect_context

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Change this to a secure key in production

DATABASE = 'users.db'

# Database helper functions
def get_db():
    """Get database connection"""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_db(exception):
    """Close database connection"""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    """Initialize database with required tables"""
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        
        # Create user_profile table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_profile (
                user_id TEXT PRIMARY KEY,
                ui_language TEXT NOT NULL,
                visitor_type TEXT NOT NULL,
                distance_pref TEXT NOT NULL,
                interest_mode TEXT NOT NULL
            )
        ''')
        
        # Create preferences table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                preferred_themes TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES user_profile(user_id)
            )
        ''')
        
        db.commit()

def user_has_profile(user_id):
    """Check if user has completed onboarding"""
    if not user_id:
        return False
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT user_id FROM user_profile WHERE user_id = ?', (user_id,))
    return cursor.fetchone() is not None

def login_required(f):
    """Decorator to check if user is logged in"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # For demo purposes, we'll use session to store user_id
        # In production, integrate with your actual authentication system
        if 'user_id' not in session:
            # For testing: set a default user_id if not logged in
            session['user_id'] = 'demo_user_1'
        return f(*args, **kwargs)
    return decorated_function

@app.before_request
def check_onboarding():
    """Check if user needs to complete onboarding"""
    # Skip check for onboarding routes, logout, static files, and reset_profile
    if request.endpoint in ['onboarding', 'submit_onboarding', 'logout', 'static', 'reset_profile']:
        return
    
    # Get user_id from session (or set default for demo)
    user_id = session.get('user_id', 'demo_user_1')
    if not user_id:
        session['user_id'] = 'demo_user_1'
        user_id = 'demo_user_1'
    
    # Check if user has completed onboarding
    if not user_has_profile(user_id):
        return redirect(url_for('onboarding'))

@app.route('/')
def index():
    """Main index page"""
    user_id = session.get('user_id', 'demo_user_1')
    if not user_has_profile(user_id):
        return redirect(url_for('onboarding'))
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM user_profile WHERE user_id = ?', (user_id,))
    profile = cursor.fetchone()
    
    cursor.execute('SELECT preferred_themes FROM preferences WHERE user_id = ?', (user_id,))
    themes = [row['preferred_themes'] for row in cursor.fetchall()]
    
    return render_template('index.html', profile=profile, themes=themes)

@app.route('/onboarding')
@login_required
def onboarding():
    """Render the onboarding quiz"""
    user_id = session.get('user_id', 'demo_user_1')
    
    # If user already has a profile, redirect to gallery
    if user_has_profile(user_id):
        return redirect(url_for('museum_gallery'))
    
    return render_template('onboarding.html')

@app.route('/submit_onboarding', methods=['POST'])
@login_required
def submit_onboarding():
    """Handle onboarding form submission"""
    user_id = session.get('user_id', 'demo_user_1')
    
    # Get form data
    ui_language = request.form.get('ui_language')
    visitor_type = request.form.get('visitor_type')
    distance_pref = request.form.get('distance_pref')
    interest_mode = request.form.get('interest_mode')
    preferred_themes = request.form.getlist('preferred_themes')
    
    # Validate required fields
    if not all([ui_language, visitor_type, distance_pref, interest_mode]):
        return render_template('onboarding.html', 
                             error='Please fill in all required fields.')
    
    if not preferred_themes:
        return render_template('onboarding.html', 
                             error='Please select at least one theme preference.')
    
    try:
        db = get_db()
        cursor = db.cursor()
        
        # Insert user profile
        cursor.execute('''
            INSERT INTO user_profile (user_id, ui_language, visitor_type, distance_pref, interest_mode)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, ui_language, visitor_type, distance_pref, interest_mode))
        
        # Insert theme preferences (multiple rows)
        for theme in preferred_themes:
            cursor.execute('''
                INSERT INTO preferences (user_id, preferred_themes)
                VALUES (?, ?)
            ''', (user_id, theme))
        
        db.commit()
        
        # Set language preference in session for next page
        lang_code = 'fr' if ui_language == 'French' else 'en'
        session['preferred_language'] = lang_code
        
        # Redirect with language preference
        response = redirect(url_for('museum_gallery'))
        # Set a cookie or use session to pass language preference
        return response
    
    except sqlite3.IntegrityError:
        # User profile already exists, update instead
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute('''
            UPDATE user_profile 
            SET ui_language = ?, visitor_type = ?, distance_pref = ?, interest_mode = ?
            WHERE user_id = ?
        ''', (ui_language, visitor_type, distance_pref, interest_mode, user_id))
        
        # Delete existing preferences and insert new ones
        cursor.execute('DELETE FROM preferences WHERE user_id = ?', (user_id,))
        for theme in preferred_themes:
            cursor.execute('''
                INSERT INTO preferences (user_id, preferred_themes)
                VALUES (?, ?)
            ''', (user_id, theme))
        
        db.commit()
        
        # Set language preference in session for next page
        lang_code = 'fr' if ui_language == 'French' else 'en'
        session['preferred_language'] = lang_code
        
        return redirect(url_for('museum_gallery'))
    
    except Exception as e:
        return render_template('onboarding.html', 
                             error=f'An error occurred: {str(e)}')

@app.route('/reset_profile', methods=['GET', 'POST'])
def reset_profile():
    """Reset user profile to allow re-onboarding (for testing)"""
    user_id = session.get('user_id', 'demo_user_1')
    
    if request.method == 'POST':
        db = get_db()
        cursor = db.cursor()
        
        # Delete user preferences
        cursor.execute('DELETE FROM preferences WHERE user_id = ?', (user_id,))
        
        # Delete user profile
        cursor.execute('DELETE FROM user_profile WHERE user_id = ?', (user_id,))
        
        db.commit()
        
        # Clear session
        session.clear()
        
        return redirect(url_for('onboarding'))
    
    # GET request - show confirmation page
    return '''
    <html>
        <head><title>Reset Profile</title></head>
        <body style="font-family: Arial; padding: 40px; text-align: center;">
            <h1>Reset Profile</h1>
            <p>This will delete your profile and allow you to go through onboarding again.</p>
            <form method="POST">
                <button type="submit" style="padding: 10px 20px; background: #8A734D; color: white; border: none; border-radius: 5px; cursor: pointer;">
                    Reset Profile
                </button>
            </form>
            <br>
            <a href="/" style="color: #8A734D;">Cancel - Go Back</a>
        </body>
    </html>
    '''

@app.route('/track_interaction', methods=['POST'])
def track_interaction():
    """Receive and log interaction tracking data from frontend"""
    try:
        # Get JSON data from request (handles both JSON and sendBeacon blob)
        data = request.get_json()
        
        # If get_json() returns None, try to parse the raw data (for sendBeacon)
        if not data and request.data:
            try:
                import json
                data = json.loads(request.data.decode('utf-8'))
            except:
                pass
        
        if not data:
            print("ERROR: No data received in tracking request")
            return {'status': 'error', 'message': 'No data received'}, 400
        
        # Extract tracking data
        museum_id = data.get('museum_id', 'N/A')
        interaction_type = data.get('interaction_type', 'N/A')
        duration_sec = data.get('duration_sec')
        timestamp = data.get('timestamp', 'N/A')
        
        # Get user_id from session
        user_id = session.get('user_id', 'demo_user_1')
        
        # Simple console logging
        if interaction_type == 'reading' and duration_sec is not None:
            print(f"Logged {interaction_type} for museum {museum_id} - Duration: {duration_sec} seconds")
        elif interaction_type == 'favorite':
            favorite_state = data.get('favorite_state', 'N/A')
            print(f"Logged {interaction_type} for museum {museum_id} - State: {favorite_state}")
        else:
            print(f"Logged {interaction_type} for museum {museum_id}")
        
        # Additional debug info
        print(f"  Timestamp: {timestamp}")
        if duration_sec:
            print(f"  Duration: {duration_sec} seconds")
        
        # Process interaction through scoring system
        try:
            scoring_result = process_interaction(
                user_id=user_id,
                museum_id=museum_id,
                interaction_type=interaction_type,
                duration_sec=duration_sec
            )
            
            # Log scoring results
            print(f"\n  📊 SCORING RESULTS:")
            print(f"     Points Earned: {scoring_result['points_earned']}")
            if scoring_result.get('theme'):
                print(f"     Theme: {scoring_result['theme']}")
                print(f"     Theme Score: {scoring_result['updates'].get('theme_score', 0)}")
            print(f"     Museum Popularity: {scoring_result['updates'].get('museum_popularity', 0)}")
            print(f"     Total Engagement: {scoring_result['updates'].get('engagement_score', 0)}")
            print()
        
        except Exception as e:
            print(f"  ⚠️  Scoring error (non-fatal): {str(e)}")
        
        # TODO: In production, save this data to a database table
        # Example:
        # db = get_db()
        # cursor = db.cursor()
        # cursor.execute('''
        #     INSERT INTO user_interactions (user_id, museum_id, interaction_type, duration_sec, timestamp)
        #     VALUES (?, ?, ?, ?, ?)
        # ''', (user_id, museum_id, interaction_type, duration_sec, timestamp))
        # db.commit()
        
        return {'status': 'success', 'message': 'Interaction tracked'}, 200
    
    except Exception as e:
        # Log error but don't break the frontend
        print(f"ERROR tracking interaction: {str(e)}")
        return {'status': 'error', 'message': str(e)}, 500

@app.route('/user_profile')
def view_user_profile():
    """View the dynamic user profile dashboard with analytics and explainability"""
    user_id = session.get('user_id', 'demo_user_1')
    
    # Get dynamic profile (scoring data)
    dynamic_profile = get_user_profile(user_id)
    
    # Get onboarding profile data
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM user_profile WHERE user_id = ?', (user_id,))
    onboarding_profile = cursor.fetchone()
    
    cursor.execute('SELECT preferred_themes FROM preferences WHERE user_id = ?', (user_id,))
    themes = [row['preferred_themes'] for row in cursor.fetchall()]
    
    # Get museum popularity stats for top museums
    from scoring import mock_db
    top_museums = sorted(
        mock_db['museum_popularity'].items(),
        key=lambda x: x[1],
        reverse=True
    )[:5]
    
    museum_stats = []
    for museum_id, popularity in top_museums:
        stats = get_museum_stats(museum_id)
        museum_stats.append(stats)
    
    # Get current adaptation settings for explainability
    context = detect_context(request)
    user_profile_dict = None
    if onboarding_profile:
        user_profile_dict = dict(onboarding_profile)
    
    active_settings = get_active_settings(
        user_profile=user_profile_dict,
        context=context
    )
    
    # Calculate engagement metrics
    total_interactions = dynamic_profile.get('engagement_score', 0)
    theme_count = len(dynamic_profile.get('theme_affinities', {}))
    
    # Calculate engagement level
    if total_interactions >= 20:
        engagement_level = 'High'
        engagement_color = '#27ae60'
    elif total_interactions >= 10:
        engagement_level = 'Medium'
        engagement_color = '#f39c12'
    else:
        engagement_level = 'Low'
        engagement_color = '#e74c3c'
    
    return render_template('user_profile.html', 
                         dynamic_profile=dynamic_profile,
                         onboarding_profile=onboarding_profile,
                         themes=themes,
                         museum_stats=museum_stats,
                         active_settings=active_settings,
                         context=context,
                         engagement_level=engagement_level,
                         engagement_color=engagement_color,
                         total_interactions=total_interactions,
                         theme_count=theme_count)

@app.route('/favorites')
@login_required
def favorites():
    """Display user's favorite museums"""
    # Get all museums (frontend will filter by localStorage favorites)
    museums_data = get_all_museums()
    
    return render_template('favorites.html', museums=museums_data)

@app.route('/history')
@login_required
def history():
    """Display user's museum visit history"""
    # Get all museums (frontend will filter by localStorage history)
    museums_data = get_all_museums()
    
    return render_template('history.html', museums=museums_data)

@app.route('/logout')
def logout():
    """Logout user and redirect to onboarding"""
    user_id = session.get('user_id', 'demo_user_1')
    
    # Delete user profile and preferences from database
    try:
        db = get_db()
        cursor = db.cursor()
        
        # Delete user preferences
        cursor.execute('DELETE FROM preferences WHERE user_id = ?', (user_id,))
        
        # Delete user profile
        cursor.execute('DELETE FROM user_profile WHERE user_id = ?', (user_id,))
        
        db.commit()
    except Exception as e:
        print(f"Error deleting profile on logout: {e}")
    
    # Clear session
    session.clear()
    
    # Redirect to onboarding
    return redirect(url_for('onboarding'))

def get_all_museums():
    """Helper function to get all museums (placeholder - replace with DB query)"""
    return [
        {
            'id': '1',
            'name': 'Louvre Museum',
            'location': 'Paris',
            'description': 'The world\'s largest art museum and a historic monument in Paris, France.',
            'image_url': 'https://via.placeholder.com/400x300?text=Louvre',
            'theme': 'Art',
            'distance': 2.5
        },
        {
            'id': '2',
            'name': 'Musée d\'Orsay',
            'location': 'Paris',
            'description': 'A museum in Paris, France, on the Left Bank of the Seine, housed in the former Gare d\'Orsay.',
            'image_url': 'https://via.placeholder.com/400x300?text=Orsay',
            'theme': 'Art',
            'distance': 3.1
        },
        {
            'id': '3',
            'name': 'Musée de l\'Histoire de France',
            'location': 'Versailles',
            'description': 'A museum dedicated to French history located in the Palace of Versailles.',
            'image_url': 'https://via.placeholder.com/400x300?text=History',
            'theme': 'History',
            'distance': 18.5
        },
        {
            'id': '4',
            'name': 'Centre Pompidou',
            'location': 'Paris',
            'description': 'A complex building in the Beaubourg area housing the largest museum for modern art in Europe.',
            'image_url': 'https://via.placeholder.com/400x300?text=Pompidou',
            'theme': 'Art',
            'distance': 1.8
        },
        {
            'id': '5',
            'name': 'Musée Rodin',
            'location': 'Paris',
            'description': 'A museum dedicated to the works of the French sculptor Auguste Rodin.',
            'image_url': 'https://via.placeholder.com/400x300?text=Rodin',
            'theme': 'Art',
            'distance': 4.2
        },
        {
            'id': '6',
            'name': 'Musée de la Science',
            'location': 'Paris',
            'description': 'A science museum featuring interactive exhibits and scientific discoveries.',
            'image_url': 'https://via.placeholder.com/400x300?text=Science',
            'theme': 'Science',
            'distance': 5.5
        },
        {
            'id': '7',
            'name': 'Musée du Patrimoine Local',
            'location': 'Lyon',
            'description': 'A museum showcasing local heritage and cultural traditions of the region.',
            'image_url': 'https://via.placeholder.com/400x300?text=Heritage',
            'theme': 'Local Heritage',
            'distance': 25.0
        },
        {
            'id': '8',
            'name': 'Musée Picasso',
            'location': 'Paris',
            'description': 'A museum housing one of the largest collections of works by Pablo Picasso.',
            'image_url': 'https://via.placeholder.com/400x300?text=Picasso',
            'theme': 'Art',
            'distance': 3.8
        },
        {
            'id': '9',
            'name': 'Musée d\'Histoire Naturelle',
            'location': 'Paris',
            'description': 'A natural history museum with extensive collections of fossils, minerals, and specimens.',
            'image_url': 'https://via.placeholder.com/400x300?text=Natural+History',
            'theme': 'Science',
            'distance': 2.3
        },
        {
            'id': '10',
            'name': 'Château de Chambord',
            'location': 'Chambord',
            'description': 'A Renaissance château showcasing French architectural heritage and royal history.',
            'image_url': 'https://via.placeholder.com/400x300?text=Chambord',
            'theme': 'Local Heritage',
            'distance': 120.0
        },
        {
            'id': '11',
            'name': 'Musée des Beaux-Arts',
            'location': 'Lyon',
            'description': 'One of France\'s largest fine arts museums with collections spanning from antiquity to modern art.',
            'image_url': 'https://via.placeholder.com/400x300?text=Beaux+Arts',
            'theme': 'Art',
            'distance': 28.0
        },
        {
            'id': '12',
            'name': 'Cité des Sciences',
            'location': 'Paris',
            'description': 'Europe\'s largest science museum with interactive exhibits and planetarium.',
            'image_url': 'https://via.placeholder.com/400x300?text=Cite+Sciences',
            'theme': 'Science',
            'distance': 8.0
        }
    ]

@app.route('/museum_gallery')
def museum_gallery():
    """Render museum gallery page with adaptive settings"""
    # Get user profile
    user_id = session.get('user_id', 'demo_user_1')
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM user_profile WHERE user_id = ?', (user_id,))
    user_profile = cursor.fetchone()
    
    # Detect current context
    context = detect_context(request)
    
    # Get active adaptation settings
    user_profile_dict = None
    if user_profile:
        user_profile_dict = dict(user_profile)
    
    active_settings = get_active_settings(
        user_profile=user_profile_dict,
        context=context
    )
    
    # Get all museums
    museums = get_all_museums()
    
    # Apply max_results limit
    museums = museums[:active_settings['max_results']]
    
    # Generate adaptation log message
    adaptation_log = get_adaptation_log_message(active_settings)
    
    return render_template('museum_gallery.html', 
                         museums=museums, 
                         settings=active_settings,
                         adaptation_log=adaptation_log)

@app.route('/museum/<museum_id>')
def museum_detail(museum_id):
    """Render museum detail page (placeholder - replace with actual data)"""
    # TODO: Replace with actual database query
    museums_data = {
        '1': {
            'id': '1',
            'name': 'Louvre Museum',
            'location': 'Paris, France',
            'description': 'The world\'s largest art museum and a historic monument in Paris, France. A central landmark of the city, it is located on the Right Bank of the Seine in the city\'s 1st arrondissement. Approximately 38,000 objects from prehistory to the 21st century are exhibited over an area of 72,735 square meters.',
            'image_url': 'https://via.placeholder.com/800x500?text=Louvre+Museum',
            'theme': 'Art',
            'distance': 2.5,
            'opening_hours': 'Monday to Sunday: 9:00 AM - 6:00 PM',
            'website': 'https://www.louvre.fr'
        },
        '2': {
            'id': '2',
            'name': 'Musée d\'Orsay',
            'location': 'Paris, France',
            'description': 'A museum in Paris, France, on the Left Bank of the Seine. It is housed in the former Gare d\'Orsay, a Beaux-Arts railway station built between 1898 and 1900. The museum holds mainly French art dating from 1848 to 1914, including paintings, sculptures, furniture, and photography.',
            'image_url': 'https://via.placeholder.com/800x500?text=Musee+dOrsay',
            'theme': 'Art',
            'distance': 3.1,
            'opening_hours': 'Tuesday to Sunday: 9:30 AM - 6:00 PM',
            'website': 'https://www.musee-orsay.fr'
        },
        '3': {
            'id': '3',
            'name': 'Musée de l\'Histoire de France',
            'location': 'Versailles, France',
            'description': 'A museum dedicated to French history located in the Palace of Versailles. It showcases the rich history of France from ancient times to the modern era, with a particular focus on the French Revolution and the Napoleonic era.',
            'image_url': 'https://via.placeholder.com/800x500?text=History+Museum',
            'theme': 'History',
            'distance': 18.5,
            'opening_hours': 'Tuesday to Sunday: 9:00 AM - 5:30 PM',
            'website': 'https://www.chateauversailles.fr'
        }
    }
    
    museum = museums_data.get(museum_id)
    if not museum:
        return "Museum not found", 404
    
    return render_template('museum_detail.html', museum=museum)

if __name__ == '__main__':
    # Initialize database on startup
    init_db()
    app.run(debug=True)
