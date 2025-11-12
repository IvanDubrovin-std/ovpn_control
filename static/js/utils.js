/**
 * Utility Functions for OpenVPN Control Panel
 */

/**
 * Get CSRF token from cookies
 * @param {string} name - Cookie name
 * @returns {string|null} - Cookie value or null
 */
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

/**
 * Show status message
 * @param {string} message - Message to display
 * @param {string} type - Message type (info, success, warning, danger)
 */
function showStatus(message, type = 'info') {
    const statusDiv = document.getElementById('ssh-status');
    const messageSpan = document.getElementById('status-message');
    
    if (statusDiv && messageSpan) {
        statusDiv.className = `alert alert-${type} m-3 mb-0`;
        messageSpan.textContent = message;
        statusDiv.style.display = 'block';
    }
}

/**
 * Hide status message
 */
function hideStatus() {
    const statusDiv = document.getElementById('ssh-status');
    if (statusDiv) {
        statusDiv.style.display = 'none';
    }
}

/**
 * Show loading state on button
 * @param {HTMLElement} button - Button element
 * @param {string} message - Loading message
 * @returns {string} - Original button HTML
 */
function showButtonLoading(button, message = 'Загрузка...') {
    const originalHTML = button.innerHTML;
    button.disabled = true;
    button.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${message}`;
    return originalHTML;
}

/**
 * Restore button state
 * @param {HTMLElement} button - Button element
 * @param {string} originalHTML - Original button HTML
 */
function restoreButton(button, originalHTML) {
    button.disabled = false;
    button.innerHTML = originalHTML;
}

/**
 * Show confirmation dialog
 * @param {string} message - Confirmation message
 * @returns {boolean} - User confirmation
 */
function confirmAction(message) {
    return confirm(message);
}

/**
 * Show alert message
 * @param {string} message - Alert message
 * @param {string} title - Alert title (optional)
 */
function showAlert(message, title = '') {
    if (title) {
        alert(`${title}\n\n${message}`);
    } else {
        alert(message);
    }
}

/**
 * Reload page after delay
 * @param {number} delay - Delay in milliseconds (default: 2000)
 */
function reloadPage(delay = 2000) {
    setTimeout(() => {
        location.reload();
    }, delay);
}

/**
 * Format date to local string
 * @param {string|Date} date - Date to format
 * @returns {string} - Formatted date string
 */
function formatDate(date) {
    const d = new Date(date);
    return d.toLocaleString('ru-RU', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

/**
 * Escape HTML special characters
 * @param {string} text - Text to escape
 * @returns {string} - Escaped text
 */
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

/**
 * Validate email format
 * @param {string} email - Email to validate
 * @returns {boolean} - True if valid
 */
function isValidEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

/**
 * Validate client name format
 * @param {string} name - Name to validate
 * @returns {boolean} - True if valid
 */
function isValidClientName(name) {
    const re = /^[a-zA-Z0-9_-]+$/;
    return re.test(name);
}

/**
 * Handle API error
 * @param {Error} error - Error object
 * @param {string} context - Error context
 */
function handleApiError(error, context = 'Операция') {
    console.error(`${context} error:`, error);
    showAlert(`${context}: ${error.message}`, 'Ошибка');
}

/**
 * Make API request with error handling
 * @param {string} url - API endpoint URL
 * @param {Object} options - Fetch options
 * @returns {Promise<Object>} - Response data
 */
async function apiRequest(url, options = {}) {
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        }
    };
    
    const mergedOptions = {
        ...defaultOptions,
        ...options,
        headers: {
            ...defaultOptions.headers,
            ...options.headers
        }
    };
    
    const response = await fetch(url, mergedOptions);
    
    if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.error || `HTTP error! status: ${response.status}`);
    }
    
    return response.json();
}

/**
 * Download file from blob
 * @param {Blob} blob - File blob
 * @param {string} filename - File name
 */
function downloadBlob(blob, filename) {
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.style.display = 'none';
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
}
