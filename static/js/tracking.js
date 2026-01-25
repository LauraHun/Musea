/**
 * Interaction Tracking System for Adaptive Museum Explorer
 * Tracks user interactions: clicks, favorites, and reading time
 */

// Configuration
const TRACKING_ENDPOINT = '/track_interaction';

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
            console.warn('Tracking data not sent (backend may be in development):', response.status);
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
 * Initialize reading timer on museum detail page
 */
function initializeReadingTimer() {
    // Check if we're on a museum detail page
    const isDetailPage = document.querySelector('.museum-detail, [data-page="detail"]');
    
    if (isDetailPage) {
        readingTimer = new ReadingTimer();
        readingTimer.start();
        
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
 * Initialize all tracking when DOM is ready
 */
function initializeTracking() {
    // Wait for DOM to be fully loaded
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            initializeMuseumCardTracking();
            initializeReadingTimer();
        });
    } else {
        // DOM is already loaded
        initializeMuseumCardTracking();
        initializeReadingTimer();
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
