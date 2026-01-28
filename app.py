from flask import Flask, render_template, request, redirect, url_for, session, g, jsonify
import sqlite3
import os
from functools import wraps
from scoring import process_interaction
from adaptation import get_active_settings, get_adaptation_log_message, detect_context
import db_manager

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Change this to a secure key in production

DATABASE = 'users.db'

# Template filter: choose best image URL for a museum
@app.template_filter('museum_image_url')
def museum_image_url(museum):
    """Return a per-museum image if available, otherwise theme-based default, otherwise placeholder."""
    if not museum:
        return url_for('static', filename='placeholder.svg')
    img = (museum.get('image_url') or '').strip()
    if img:
        return img
    theme = (museum.get('theme') or '').strip()
    defaults = {
        'Art': 'https://images.unsplash.com/photo-1536924940846-227afb31e2a5?w=640',
        # History: shelves of archival books / documents
        'History': 'https://images.unsplash.com/photo-1457369804613-52c61a468e7d?w=640',
        'Science': 'https://images.unsplash.com/photo-1635070041078-e363dbe005cb?w=640',
        'Local Heritage': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=640',
    }
    return defaults.get(theme) or url_for('static', filename='placeholder.svg')


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

def login_required(f):
    """Redirect to /login if no user_id in session (pseudo-based login)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


@app.context_processor
def inject_logged_in():
    """Expose logged_in to all templates for navbar dropdown."""
    return {'logged_in': bool(session.get('user_id'))}

@app.route('/')
def index():
    """Discovery / gallery is the home when not forcing login."""
    return redirect(url_for('museum_gallery'))

@app.route('/onboarding')
def onboarding():
    """Sign-up: onboarding quiz (no login required)."""
    if session.get('user_id'):
        return redirect(url_for('museum_gallery'))
    return render_template('onboarding.html')

@app.route('/submit_onboarding', methods=['POST'])
def submit_onboarding():
    """Handle onboarding form submission; pseudo = login id, user_id = pseudo."""
    pseudo = (request.form.get('pseudo') or '').strip()
    ui_language = request.form.get('ui_language')
    visitor_type = request.form.get('visitor_type')
    distance_pref = request.form.get('distance_pref')
    interest_mode = request.form.get('interest_mode')
    preferred_themes = request.form.getlist('preferred_themes')
    hub_city = (request.form.get('hub_city') or '').strip()
    if not pseudo:
        return render_template('onboarding.html', error='Please pick a pseudo.')
    if not all([ui_language, visitor_type, distance_pref, interest_mode, hub_city]):
        return render_template('onboarding.html', error='Please fill in all required fields.')
    if not preferred_themes:
        return render_template('onboarding.html', error='Please select at least one theme preference.')
    if db_manager.get_user_by_pseudo(pseudo):
        return render_template('onboarding.html', error='This pseudo is already taken. Choose another.')
    user_id = pseudo
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            INSERT INTO user_profile (user_id, ui_language, visitor_type, distance_pref, interest_mode)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, ui_language, visitor_type, distance_pref, interest_mode))
        for theme in preferred_themes:
            cursor.execute('INSERT INTO preferences (user_id, preferred_themes) VALUES (?, ?)', (user_id, theme))
        db.commit()
    except sqlite3.IntegrityError:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            UPDATE user_profile SET ui_language = ?, visitor_type = ?, distance_pref = ?, interest_mode = ?
            WHERE user_id = ?
        ''', (ui_language, visitor_type, distance_pref, interest_mode, user_id))
        cursor.execute('DELETE FROM preferences WHERE user_id = ?', (user_id,))
        for theme in preferred_themes:
            cursor.execute('INSERT INTO preferences (user_id, preferred_themes) VALUES (?, ?)', (user_id, theme))
        db.commit()
    try:
        db_manager.save_user_profile({
            'user_id': user_id, 'pseudo': pseudo, 'ui_language': ui_language, 'visitor_type': visitor_type,
            'distance_pref': distance_pref, 'interest_mode': interest_mode, 'theme_pref': ','.join(preferred_themes),
            'hub_city': hub_city,
        })
    except Exception as e:
        return render_template('onboarding.html', error=f'Could not save profile: {str(e)}')
    session['user_id'] = user_id
    session['preferred_language'] = 'fr' if ui_language == 'French' else 'en'
    return redirect(url_for('museum_gallery'))

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
    """Log interaction; requires session user_id (logged in)."""
    if not session.get('user_id'):
        from flask import jsonify
        return jsonify({'status': 'error', 'message': 'Login required'}), 401
    try:
        data = request.get_json()
        if not data and request.data:
            try:
                import json
                data = json.loads(request.data.decode('utf-8'))
            except Exception:
                pass
        if not data:
            return jsonify({'status': 'error', 'message': 'No data received'}), 400
        museum_id = data.get('museum_id')
        interaction_type = data.get('interaction_type', 'view-details')
        duration_sec = data.get('duration_sec') or 0
        user_id = session['user_id']
        try:
            mid = int(museum_id) if museum_id is not None else None
            if mid is not None:
                db_manager.log_interaction(user_id, mid, interaction_type, float(duration_sec))
        except (TypeError, ValueError):
            # Ignore malformed museum IDs in tracking payloads
            pass
        museum_theme = None
        try:
            mid = int(museum_id) if museum_id is not None else None
            if mid is not None:
                mus = db_manager.get_museum_by_id(mid)
                if mus and mus.get('theme'):
                    museum_theme = mus.get('theme')
        except (TypeError, ValueError):
            # If theme lookup fails we still record the interaction
            pass
        # Best-effort scoring: errors here must not break tracking
        try:
            process_interaction(
                user_id=user_id,
                museum_id=museum_id,
                interaction_type=interaction_type,
                duration_sec=duration_sec,
                theme=museum_theme,
            )
        except Exception:
            # Intentionally swallowed; scoring is supplementary
            pass
        return jsonify({'status': 'success', 'message': 'Interaction tracked'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/user_profile')
@login_required
def view_user_profile():
    """View the dynamic user profile dashboard; all data from musea.db."""
    user_id = session.get('user_id')
    engagement = db_manager.get_engagement_for_user(user_id)
    total_interactions = engagement['total_interactions']
    engagement_score = engagement['engagement_score']

    theme_affinities = db_manager.get_theme_affinity_from_interactions(user_id)
    dynamic_profile = {
        'user_id': user_id,
        'engagement_score': engagement_score,
        'theme_affinities': theme_affinities,
        'top_themes': sorted(theme_affinities.items(), key=lambda x: -x[1])[:3],
        'total_themes': len(theme_affinities),
    }

    onboarding_profile = db_manager.get_user_profile(user_id)
    theme_pref = (onboarding_profile.get('theme_pref') or '').strip() if onboarding_profile else ''
    themes = [t.strip() for t in theme_pref.split(',') if t.strip()]

    # Most popular museums from DB (museums.popularity_score), not in-memory mock
    all_museums = db_manager.get_all_museums()
    top5 = sorted(all_museums, key=lambda m: -(m.get('popularity_score') or 0))[:5]
    museum_stats = [
        {'museum_id': m['id'], 'name': m.get('name'), 'theme': m.get('theme'), 'popularity_score': m.get('popularity_score') or 0}
        for m in top5
    ]

    context = detect_context(request)
    user_profile_dict = dict(onboarding_profile) if onboarding_profile else None
    active_settings = get_active_settings(user_profile=user_profile_dict, context=context)
    theme_count = len(dynamic_profile.get('theme_affinities', {}))

    # Engagement level colors tuned to be softer and match Musea palette
    if total_interactions >= 20:
        # Brighter green so it stands out on the brown gradient background
        engagement_level, engagement_color = 'High', '#3DDC97'
    elif total_interactions >= 10:
        engagement_level, engagement_color = 'Medium', '#f1c40f' # warm amber
    else:
        engagement_level, engagement_color = 'Low', '#e67e22'    # softer orange-red

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
    """Display user's favorite museums (frontend filters by localStorage)."""
    return render_template('favorites.html', museums=db_manager.get_all_museums())

@app.route('/history')
@login_required
def history():
    """Display user's museum visit history (frontend filters by localStorage)."""
    return render_template('history.html', museums=db_manager.get_all_museums())

@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def profile_edit():
    """Edit interests (theme_pref), distance_pref and discovery style (interest_mode)."""
    user_id = session.get('user_id')
    profile = db_manager.get_user_profile(user_id) or {}
    if request.method == 'POST':
        preferred_themes = request.form.getlist('preferred_themes')
        distance_pref = (request.form.get('distance_pref') or 'medium').strip()
        interest_mode = (request.form.get('interest_mode') or profile.get('interest_mode') or 'balanced').strip()
        theme_pref = ','.join(preferred_themes) if preferred_themes else (profile.get('theme_pref') or '')
        db_manager.save_user_profile({
            'user_id': user_id,
            'pseudo': profile.get('pseudo') or user_id,
            'ui_language': profile.get('ui_language') or '',
            'visitor_type': profile.get('visitor_type') or '',
            'distance_pref': distance_pref,
            'interest_mode': interest_mode,
            'theme_pref': theme_pref,
        })
        return redirect(url_for('view_user_profile'))
    themes = (profile.get('theme_pref') or '').split(',')
    themes = [t.strip() for t in themes if t.strip()]
    return render_template('profile_edit.html', profile=profile, current_themes=themes)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Pseudo-based login: check pseudo in DB, set session['user_id'], redirect to Discovery."""
    if request.method == 'GET':
        next_url = request.args.get('next', url_for('museum_gallery'))
        return render_template('login.html', next=next_url, error=request.args.get('error'))
    pseudo = (request.form.get('pseudo') or '').strip()
    time_available_raw = (request.form.get('time_available') or '').strip()
    if not pseudo:
        return render_template('login.html', next=request.form.get('next', url_for('museum_gallery')), error='Please enter your pseudo.')
    if not time_available_raw:
        return render_template('login.html', next=request.form.get('next', url_for('museum_gallery')), error='Please select how much time you have today.')
    try:
        time_available_min = int(time_available_raw)
    except ValueError:
        return render_template('login.html', next=request.form.get('next', url_for('museum_gallery')), error='Invalid time selection.')
    user = db_manager.get_user_by_pseudo(pseudo)
    if not user:
        return render_template('login.html', next=request.form.get('next', url_for('museum_gallery')), error='Unknown pseudo. Sign up first.')
    session['user_id'] = user['user_id']
    # Persist today's available time so the adaptation engine can use it
    session['time_available_minutes'] = time_available_min
    return redirect(request.form.get('next') or url_for('museum_gallery'))

@app.route('/logout')
def logout():
    """Clear session and redirect to Discovery (gallery)."""
    session.clear()
    return redirect(url_for('museum_gallery'))

@app.route('/museum_gallery')
def museum_gallery():
    """
    Discovery page with two tabs:
    - "For You": 80% from interests, 20% exploration; adapts with engagement.
    - "Hidden Gems": low-popularity museums with high approval, filtered by theme_pref.
    """
    theme_param = (request.args.get('theme') or '').strip()
    current_tab = (request.args.get('tab') or 'for_you').strip().lower()
    show_all = (request.args.get('show_all') or '').strip() == '1'
    user_id = session.get('user_id')
    user_profile = db_manager.get_user_profile(user_id) if user_id else None
    context = detect_context(request)
    active_settings = get_active_settings(
        user_profile=dict(user_profile) if user_profile else None,
        context=context
    )
    max_results = active_settings['max_results']
    short_session = context.get('time_available', 60) <= 15

    if theme_param:
        # When filtering by theme, show all museums of that theme (For You tab).
        museums = db_manager.get_museums_by_theme(theme_param)
    elif current_tab == 'hidden':
        # Hidden gems: user-specific when logged in, global underrated when anonymous.
        # For short sessions we still want to know if there are more items to show when user clicks "See more".
        hidden_limit = max_results
        if short_session or show_all:
            hidden_limit = max(hidden_limit, 100)
        museums = db_manager.get_hidden_gems(user_id=user_id, max_results=hidden_limit)
    elif user_id:
        engagement = db_manager.get_engagement_for_user(user_id)
        # Discovery ordering for all museums: personalised but still exploratory.
        museums = db_manager.get_museums_for_discovery_all(
            user_id,
            exploration_ratio=0.2,
            engagement_score=engagement.get('engagement_score'),
        )
    else:
        # Anonymous users: show all museums, most popular first.
        museums = sorted(
            db_manager.get_all_museums(),
            key=lambda m: (-(m.get('popularity_score') or 0), (m.get('name') or "")),
        )
    # Attach distance_km and apply distance preference bands for logged-in users
    if user_id:
        museums = db_manager._annotate_and_filter_by_distance(user_id, museums, max_km=50.0)

    # Apply time-based limiting for short sessions, but allow "See more" to reveal the rest.
    has_more = False
    if short_session and not show_all:
        limited = museums[:max_results]
        has_more = len(museums) > len(limited)
    else:
        limited = museums

    # Precompute URL for "See more" button, preserving current filters/tab.
    see_more_url = None
    if has_more:
        url_kwargs = {}
        if theme_param:
            url_kwargs['theme'] = theme_param
        if current_tab == 'hidden':
            url_kwargs['tab'] = 'hidden'
        url_kwargs['show_all'] = 1
        see_more_url = url_for('museum_gallery', **url_kwargs)
    available_themes = db_manager.get_distinct_themes()
    adaptation_log = get_adaptation_log_message(active_settings)
    return render_template(
        'museum_gallery.html',
        museums=limited,
        settings=active_settings,
        adaptation_log=adaptation_log,
        available_themes=available_themes,
        current_theme=theme_param or None,
        current_tab=current_tab,
        has_more=has_more,
        see_more_url=see_more_url,
    )

@app.route('/museum/<museum_id>')
def museum_detail(museum_id):
    """Render museum detail page; data from musea.db."""
    try:
        museum = db_manager.get_museum_by_id(int(museum_id))
    except (TypeError, ValueError):
        museum = None
    if not museum:
        return "Museum not found", 404
    user_id = session.get('user_id')
    if user_id:
        annotated = db_manager._annotate_and_filter_by_distance(user_id, [museum], max_km=10_000)
        if annotated:
            museum = annotated[0]
    similar = db_manager.get_similar_museums(int(museum_id), max_results=3)
    return render_template('museum_detail.html', museum=museum, similar_museums=similar)


@app.route('/feedback', methods=['POST'])
@login_required
def feedback():
    """
    Explicit thumbs-up / thumbs-down feedback endpoint.

    - Ensures a single vote per user/museum (using interactions table).
    - Increments museums.thumbs_up / museums.thumbs_down.
    - Logs an interaction row and updates in-memory engagement via scoring.process_interaction.
    """
    user_id = session.get('user_id')
    try:
        data = request.get_json() or {}
    except Exception:
        data = {}
    museum_id = data.get('museum_id')
    direction = data.get('direction')

    if not museum_id or not direction:
        return jsonify({'status': 'error', 'message': 'museum_id and direction are required'}), 400

    try:
        mid = int(museum_id)
    except (TypeError, ValueError):
        return jsonify({'status': 'error', 'message': 'Invalid museum_id'}), 400

    try:
        feedback_result = db_manager.submit_feedback(user_id=user_id, museum_id=mid, direction=direction)
    except ValueError as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
    except Exception:
        return jsonify({'status': 'error', 'message': 'Could not record feedback'}), 500

    # If the user has already voted, do not change scores; just report back.
    if feedback_result.get('status') == 'already_voted':
        return jsonify({
            'status': 'already_voted',
            'message': 'You have already voted for this museum.',
            'existing': feedback_result.get('existing'),
        }), 200

    # Also update in-memory scoring / engagement model for dashboards.
    interaction_type = feedback_result.get('click_type') or 'thumbs_up'
    museum_theme = None
    try:
        museum = db_manager.get_museum_by_id(mid)
        if museum and museum.get('theme'):
            museum_theme = museum.get('theme')
    except Exception:
        pass
    # Best-effort scoring: errors here must not affect the response
    try:
        process_interaction(
            user_id=user_id,
            museum_id=str(mid),
            interaction_type=interaction_type,
            duration_sec=0,
            theme=museum_theme,
        )
    except Exception:
        # Non-fatal; DB already updated
        pass

    return jsonify({
        'status': 'ok',
        'message': 'Feedback recorded.',
        'thumbs_up': feedback_result.get('thumbs_up'),
        'thumbs_down': feedback_result.get('thumbs_down'),
        'total_interactions': feedback_result.get('total_interactions'),
        'approval_rating': feedback_result.get('approval_rating'),
        'direction': interaction_type,
    }), 200

if __name__ == '__main__':
    # Initialize database on startup
    init_db()
    app.run(debug=True)
