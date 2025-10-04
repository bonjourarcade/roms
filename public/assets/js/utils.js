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
