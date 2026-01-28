/**
 * Interaction Tracking System for Adaptive Museum Explorer
 * Tracks user interactions: clicks, favorites, and reading time
 */

// Configuration
const TRACKING_ENDPOINT = '/track_interaction';
const FEEDBACK_ENDPOINT = '/feedback';

/**
 * Save or remove favorite museum
 */
function saveFavorite(museumId, isFavorited) {
    let favorites = JSON.parse(localStorage.getItem('user_favorites') || '[]');
    
    if (isFavorited) {
        // Add to favorites if not already there
        if (!favorites.includes(museumId)) {
            favorites.push(museumId);
        }
    } else {
        // Remove from favorites
        favorites = favorites.filter(id => id !== museumId);
    }
    
    localStorage.setItem('user_favorites', JSON.stringify(favorites));
}

/**
 * Get all favorite museum IDs
 */
function getFavorites() {
    return JSON.parse(localStorage.getItem('user_favorites') || '[]');
}

/**
 * Check if museum is favorited
 */
function isFavorited(museumId) {
    const favorites = getFavorites();
    return favorites.includes(museumId);
}

/**
 * Save museum to history (most recent first)
 */
function saveToHistory(museumId) {
    let history = JSON.parse(localStorage.getItem('user_history') || '[]');
    
    // Remove if already exists (to avoid duplicates)
    history = history.filter(id => id !== museumId);
    
    // Add to beginning (most recent first)
    history.unshift(museumId);
    
    // Limit history to last 50 items
    if (history.length > 50) {
        history = history.slice(0, 50);
    }
    
    localStorage.setItem('user_history', JSON.stringify(history));
}

/**
 * Get history of visited museums (most recent first)
 */
function getHistory() {
    return JSON.parse(localStorage.getItem('user_history') || '[]');
}

/**
 * Send tracking data to the backend
 * @param {Object} data - Tracking data object
 */
async function sendTrackingData(data) {
    try {
        const response = await fetch(TRACKING_ENDPOINT, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        });

        // Handle errors gracefully - don't break the UI
        if (!response.ok) {
            if (response.status === 401) {
                // Logged-out users: tracking skipped until they log in
                console.debug('Tracking skipped (login required)');
            } else {
                console.warn('Tracking data not sent (backend may be in development):', response.status);
            }
            return false;
        }

        return true;
    } catch (error) {
        // Silently handle network errors - don't break the UI
        console.warn('Tracking error (backend may be in development):', error.message);
        return false;
    }
}

/**
 * Track museum card interactions (clicks and favorites)
 */
function initializeMuseumCardTracking() {
    // Track "View Details" button clicks
    document.querySelectorAll('.view-details-btn, [data-action="view-details"]').forEach(button => {
        button.addEventListener('click', function(e) {
            // Do not also trigger the card-level click handler
            e.stopPropagation();

            const museumCard = this.closest('.museum-card, [data-museum-id]');
            if (!museumCard) return;

            const museumId = museumCard.getAttribute('data-museum-id') || 
                           this.getAttribute('data-museum-id');
            
            if (museumId) {
                // Save to history
                saveToHistory(museumId);
                
                const trackingData = {
                    museum_id: museumId,
                    interaction_type: 'click',
                    timestamp: new Date().toISOString()
                };
                
                sendTrackingData(trackingData);
            }
        });
    });

    // Track "Favorite" button clicks
    document.querySelectorAll('.favorite-btn, [data-action="favorite"]').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault(); // Prevent default link behavior if it's an <a> tag
            e.stopPropagation(); // Prevent event bubbling

            // On the dedicated favorites page, let page-specific JS handle removal logic
            if (document.body.getAttribute('data-page') === 'favorites') {
                return;
            }
            // If not logged in, redirect to sign-in with current page as next
            if (document.body.getAttribute('data-logged-in') !== 'true') {
                const next = encodeURIComponent(window.location.pathname + window.location.search);
                window.location.href = '/login?next=' + next;
                return;
            }
            
            const museumCard = this.closest('.museum-card, [data-museum-id]');
            if (!museumCard) return;

            const museumId = museumCard.getAttribute('data-museum-id') || 
                           this.getAttribute('data-museum-id');
            
            if (museumId) {
                // Toggle favorite state visually
                this.classList.toggle('favorited');
                
                const isFavorited = this.classList.contains('favorited');
                
                // Update heart icon
                const heartIcon = this.querySelector('i');
                if (heartIcon) {
                    if (isFavorited) {
                        heartIcon.classList.remove('far');
                        heartIcon.classList.add('fas');
                        heartIcon.style.color = '#e74c3c';
                    } else {
                        heartIcon.classList.remove('fas');
                        heartIcon.classList.add('far');
                        heartIcon.style.color = '';
                    }
                }
                
                // Save/remove from favorites in localStorage
                saveFavorite(museumId, isFavorited);
                
                const trackingData = {
                    museum_id: museumId,
                    interaction_type: 'favorite',
                    favorite_state: isFavorited ? 'added' : 'removed',
                    timestamp: new Date().toISOString()
                };
                
                sendTrackingData(trackingData);
            }
        });
    });

    // Make entire museum cards clickable (except on specific controls)
    document.querySelectorAll('.museum-card').forEach(card => {
        card.addEventListener('click', function(e) {
            // Ignore clicks on favorite buttons or explicit links/buttons
            if (e.target.closest('.favorite-btn')) return;
            if (e.target.closest('.view-details-btn')) return;

            const museumId = this.getAttribute('data-museum-id');
            const detailsLink = this.querySelector('.view-details-btn');
            if (!museumId || !detailsLink || !detailsLink.href) return;

            // Save to history and track as a click, same as "View Details"
            saveToHistory(museumId);
            const trackingData = {
                museum_id: museumId,
                interaction_type: 'click',
                timestamp: new Date().toISOString()
            };
            sendTrackingData(trackingData);

            window.location.href = detailsLink.href;
        });
    });
}

/**
 * Reading Timer for Museum Detail Page
 */
class ReadingTimer {
    constructor() {
        this.startTime = null;
        this.duration = 0;
        this.isActive = false;
        this.pageVisible = true;
    }

    start() {
        if (this.isActive) return;
        
        this.startTime = Date.now();
        this.isActive = true;
        
        // Track visibility changes (tab switching, minimizing)
        document.addEventListener('visibilitychange', this.handleVisibilityChange.bind(this));
        
        // Track page unload
        window.addEventListener('beforeunload', this.stop.bind(this));
        
        // Track navigation away from page
        window.addEventListener('pagehide', this.stop.bind(this));
    }

    handleVisibilityChange() {
        if (document.hidden) {
            // Page is hidden - pause timer
            if (this.isActive && this.startTime) {
                this.duration += Date.now() - this.startTime;
                this.startTime = null;
            }
            this.pageVisible = false;
        } else {
            // Page is visible again - resume timer
            if (this.isActive && !this.startTime) {
                this.startTime = Date.now();
            }
            this.pageVisible = true;
        }
    }

    stop() {
        if (!this.isActive) return;
        
        // Calculate final duration
        if (this.startTime) {
            this.duration += Date.now() - this.startTime;
        }
        
        this.isActive = false;
        
        // Send tracking data if we have a museum ID
        const museumId = document.querySelector('[data-museum-id]')?.getAttribute('data-museum-id') ||
                        document.querySelector('.museum-detail')?.getAttribute('data-museum-id');
        
        if (museumId && this.duration > 0) {
            const durationSec = Math.round(this.duration / 1000); // Convert to seconds
            
            const trackingData = {
                museum_id: museumId,
                interaction_type: 'reading',
                duration_sec: durationSec,
                timestamp: new Date().toISOString()
            };
            
            // Use fetch with keepalive for reliable delivery on page unload
            // This is more reliable than sendBeacon for JSON data
            fetch(TRACKING_ENDPOINT, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(trackingData),
                keepalive: true // Ensures request completes even if page unloads
            }).catch(err => {
                // Silently fail - don't break user experience
                console.warn('Tracking error on page unload:', err.message);
            });
        }
        
        // Clean up event listeners
        document.removeEventListener('visibilitychange', this.handleVisibilityChange);
        window.removeEventListener('beforeunload', this.stop);
        window.removeEventListener('pagehide', this.stop);
    }
}

// Global reading timer instance
let readingTimer = null;

/**
 * Track "Visit Official Website" clicks on museum detail page (counts toward engagement)
 */
function initializeWebsiteVisitTracking() {
    const detailEl = document.querySelector('.museum-detail, [data-page="detail"]');
    if (!detailEl) return;
    const museumId = detailEl.getAttribute('data-museum-id');
    document.querySelectorAll('.museum-website a').forEach(link => {
        link.addEventListener('click', function() {
            if (museumId) {
                sendTrackingData({
                    museum_id: museumId,
                    interaction_type: 'website_visit',
                    duration_sec: 0,
                    timestamp: new Date().toISOString()
                });
            }
        });
    });
}

/**
 * Initialize reading timer on museum detail page
 */
function initializeReadingTimer() {
    // Check if we're on a museum detail page
    const isDetailPage = document.querySelector('.museum-detail, [data-page="detail"]');
    
    if (isDetailPage) {
        readingTimer = new ReadingTimer();
        readingTimer.start();
        initializeWebsiteVisitTracking();
        
        // Also track "Back" button clicks
        document.querySelectorAll('.back-btn, [data-action="back"]').forEach(button => {
            button.addEventListener('click', function() {
                if (readingTimer) {
                    readingTimer.stop();
                }
            });
        });
    }
}

/**
 * Explicit thumbs up / down feedback on museum detail page.
 * One vote per museum per user, enforced server-side.
 */
function initializeFeedbackButtons() {
    const feedbackContainers = document.querySelectorAll('.feedback-buttons[data-museum-id]');
    if (!feedbackContainers.length) return;

    feedbackContainers.forEach(container => {
        const museumId = container.getAttribute('data-museum-id');
        const buttons = container.querySelectorAll('.thumb-btn');

        buttons.forEach(btn => {
            btn.addEventListener('click', async function (e) {
                e.preventDefault();
                e.stopPropagation();

                // Require login for voting
                if (document.body.getAttribute('data-logged-in') !== 'true') {
                    const next = encodeURIComponent(window.location.pathname + window.location.search);
                    window.location.href = '/login?next=' + next;
                    return;
                }

                const direction = this.getAttribute('data-feedback');
                if (!museumId || !direction) return;

                // Optimistic UI: highlight chosen thumb
                buttons.forEach(b => b.classList.remove('selected'));
                this.classList.add('selected');

                try {
                    const res = await fetch(FEEDBACK_ENDPOINT, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            museum_id: museumId,
                            direction: direction,
                        }),
                    });

                    if (!res.ok) {
                        if (res.status === 401) {
                            const next = encodeURIComponent(window.location.pathname + window.location.search);
                            window.location.href = '/login?next=' + next;
                        }
                        return;
                    }

                    const payload = await res.json();
                    if (payload.status === 'already_voted') {
                        // Revert selection; user has already voted.
                        buttons.forEach(b => b.classList.remove('selected'));
                    }
                } catch (err) {
                    console.warn('Feedback error:', err.message);
                    // Revert optimistic UI on error
                    buttons.forEach(b => b.classList.remove('selected'));
                }
            });
        });
    });
}

/**
 * Initialize all tracking when DOM is ready
 */
function initializeTracking() {
    // Wait for DOM to be fully loaded
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            initializeMuseumCardTracking();
            initializeReadingTimer();
            initializeFeedbackButtons();
        });
    } else {
        // DOM is already loaded
        initializeMuseumCardTracking();
        initializeReadingTimer();
        initializeFeedbackButtons();
    }
}

// Auto-initialize when script loads
initializeTracking();

// Initialize favorite icons on page load
function initializeFavoriteIcons() {
    document.querySelectorAll('.favorite-btn, [data-action="favorite"]').forEach(button => {
        const museumId = button.getAttribute('data-museum-id') || 
                        button.closest('[data-museum-id]')?.getAttribute('data-museum-id');
        
        if (museumId && isFavorited(museumId)) {
            button.classList.add('favorited');
            const heartIcon = button.querySelector('i');
            if (heartIcon) {
                heartIcon.classList.remove('far');
                heartIcon.classList.add('fas');
                heartIcon.style.color = '#e74c3c';
            }
        }
    });
}

// Initialize favorites when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeFavoriteIcons);
} else {
    initializeFavoriteIcons();
}

// Export for manual initialization if needed
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        sendTrackingData,
        initializeMuseumCardTracking,
        initializeReadingTimer,
        ReadingTimer,
        saveFavorite,
        getFavorites,
        isFavorited,
        saveToHistory,
        getHistory
    };
}
