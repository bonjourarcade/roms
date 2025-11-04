/**
 * Utility functions for BonjourArcade
 */

/**
 * Normalizes a title for sorting purposes by treating "The" as a suffix
 * @param {string} title - The title to normalize
 * @returns {string} - The normalized title for sorting (e.g., "The Shining" becomes "Shining, The")
 */
function normalizeTitleForSorting(title) {
    if (!title) return '';
    
    // Convert to lowercase for consistent handling
    const lowerTitle = title.toLowerCase().trim();
    
    // Check if title starts with "The " (including space)
    if (lowerTitle.startsWith('the ')) {
        // Move "The" to the end: "The Shining" -> "Shining, The"
        const restOfTitle = title.substring(4); // Remove "The " (4 characters)
        return `${restOfTitle}, The`;
    }
    
    return title;
}

/**
 * Schedule a redirect to a given path at the next local 5:00 AM.
 * Adds a 60s guard interval to handle sleep/wake or missed timers.
 * Only activates on the play page to avoid affecting other pages by default.
 */
(function setupFiveAMRedirect() {
    try {
        const path = window.location.pathname || '';
        const isPlayPage = path === '/play' || path === '/play/' || path.startsWith('/play/');
        if (!isPlayPage) return;

        const redirectTarget = '/gotw/';
        let redirected = false;

        function redirectToGotw() {
            if (redirected) return;
            redirected = true;
            try { console.log('[5AM] Redirecting to GOTW'); } catch (_) {}
            window.location.href = redirectTarget;
        }

        function msUntilNextFiveAM(now) {
            const next = new Date(now);
            next.setSeconds(0, 0);
            next.setHours(5, 0, 0, 0);
            if (next <= now) {
                next.setDate(next.getDate() + 1);
            }
            return next.getTime() - now.getTime();
        }

        function scheduleTimeout() {
            const now = new Date();
            const delay = msUntilNextFiveAM(now);
            // Cap extremely large delays to avoid platform-specific limits
            const cappedDelay = Math.min(delay, 0x7fffffff); // ~24.8 days
            setTimeout(redirectToGotw, cappedDelay);
            try { console.log('[5AM] Scheduled redirect in', Math.round(delay / 1000), 'seconds'); } catch (_) {}
        }

        // Primary schedule
        scheduleTimeout();

        // Guard interval: check every 60s
        const guard = setInterval(() => {
            if (redirected) { clearInterval(guard); return; }
            const now = new Date();
            if (now.getHours() === 5) {
                redirectToGotw();
            }
        }, 60000);
    } catch (e) {
        // Fail-safe: never throw from utility
    }
})();
