# Interaction Tracking Implementation Guide

## Overview
This document explains the interaction tracking system implemented for the Adaptive Museum Explorer. The system tracks user interactions (clicks, favorites, and reading time) to build a dynamic user profile.

## Files Created/Modified

### 1. JavaScript Tracking (`static/js/tracking.js`)
- **Click Tracking**: Captures clicks on "View Details" buttons
- **Favorite Tracking**: Tracks favorite/unfavorite actions on heart icons
- **Reading Timer**: Measures time spent on museum detail pages
- **Error Handling**: Gracefully handles 404/500 errors without breaking the UI

### 2. Templates

#### `templates/museum_gallery.html`
- Museum cards with `data-museum-id` attributes
- "View Details" buttons with `data-action="view-details"` class
- Favorite buttons with `data-action="favorite"` class
- Includes tracking script at the bottom

#### `templates/museum_detail.html`
- Museum detail page with `data-museum-id` and `data-page="detail"` attributes
- "Back" button with `data-action="back"` class
- Reading timer automatically starts when page loads
- Includes tracking script at the bottom

### 3. Flask Route (`app.py`)
- **Route**: `/track_interaction` (POST)
- **Functionality**: Receives JSON tracking data and prints to console
- **Error Handling**: Returns appropriate HTTP status codes
- **Future**: Ready for database integration (commented TODO)

## How It Works

### Click Tracking
1. User clicks "View Details" button on a museum card
2. JavaScript captures the `data-museum-id` from the card
3. Sends POST request to `/track_interaction` with:
   ```json
   {
     "museum_id": "1",
     "interaction_type": "click",
     "timestamp": "2026-01-24T15:30:00.000Z"
   }
   ```

### Favorite Tracking
1. User clicks heart icon on a museum card
2. JavaScript toggles visual state (filled/empty heart)
3. Sends POST request with favorite state:
   ```json
   {
     "museum_id": "1",
     "interaction_type": "favorite",
     "favorite_state": "added",
     "timestamp": "2026-01-24T15:30:00.000Z"
   }
   ```

### Reading Timer
1. User navigates to museum detail page
2. Timer starts automatically when page loads
3. Timer pauses when:
   - User switches tabs (page becomes hidden)
   - User minimizes window
4. Timer stops and sends data when:
   - User clicks "Back" button
   - User navigates away (beforeunload)
   - User closes tab/window (pagehide)
5. Sends POST request with duration:
   ```json
   {
     "museum_id": "1",
     "interaction_type": "reading",
     "duration_sec": 45,
     "timestamp": "2026-01-24T15:30:00.000Z"
   }
   ```

## Data Attributes Required in Templates

### Museum Cards
```html
<div class="museum-card" data-museum-id="{{ museum.id }}">
  <button class="favorite-btn" data-action="favorite" data-museum-id="{{ museum.id }}">
  <a href="..." class="view-details-btn" data-action="view-details" data-museum-id="{{ museum.id }}">
</div>
```

### Museum Detail Page
```html
<div class="museum-detail" data-museum-id="{{ museum.id }}" data-page="detail">
  <a href="..." class="back-btn" data-action="back">
</div>
```

## Testing

### Test Click Tracking
1. Visit `/museum_gallery`
2. Click "View Details" on any museum card
3. Check Flask console for tracking data

### Test Favorite Tracking
1. Visit `/museum_gallery`
2. Click heart icon on any museum card
3. Heart should fill/empty
4. Check Flask console for tracking data

### Test Reading Timer
1. Visit `/museum/<museum_id>` (e.g., `/museum/1`)
2. Wait a few seconds
3. Click "Back" button or navigate away
4. Check Flask console for reading duration

## Error Handling

The JavaScript is designed to fail gracefully:
- Network errors are caught and logged (won't break UI)
- 404/500 responses are handled silently
- Tracking failures don't prevent normal page functionality

## Future Enhancements

### Database Integration
Uncomment and modify the TODO section in `/track_interaction` route:

```python
db = get_db()
cursor = db.cursor()
cursor.execute('''
    INSERT INTO user_interactions (user_id, museum_id, interaction_type, duration_sec, timestamp)
    VALUES (?, ?, ?, ?, ?)
''', (session.get('user_id'), data.get('museum_id'), data.get('interaction_type'), 
      data.get('duration_sec'), data.get('timestamp')))
db.commit()
```

### Database Schema Suggestion
```sql
CREATE TABLE user_interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    museum_id TEXT NOT NULL,
    interaction_type TEXT NOT NULL,  -- 'click', 'favorite', 'reading'
    duration_sec INTEGER,             -- NULL for click/favorite, set for reading
    favorite_state TEXT,              -- 'added' or 'removed' for favorites
    timestamp TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES user_profile(user_id)
);
```

## Integration Checklist

- [x] JavaScript tracking file created
- [x] Museum gallery template with data attributes
- [x] Museum detail template with reading timer
- [x] Flask route for receiving tracking data
- [x] Error handling in JavaScript
- [x] CSS styles for museum cards and detail page
- [ ] Database table for storing interactions (future)
- [ ] Analytics dashboard (future)

## Usage in Your Templates

To use tracking in your own templates:

1. **Include the tracking script**:
   ```html
   <script src="{{ url_for('static', filename='js/tracking.js') }}"></script>
   ```

2. **Add data attributes** to interactive elements:
   ```html
   <div data-museum-id="{{ museum.id }}">
     <button class="favorite-btn" data-action="favorite">❤️</button>
     <a href="..." class="view-details-btn" data-action="view-details">View</a>
   </div>
   ```

3. **For detail pages**, add:
   ```html
   <div class="museum-detail" data-museum-id="{{ museum.id }}" data-page="detail">
   ```

The tracking will work automatically!
