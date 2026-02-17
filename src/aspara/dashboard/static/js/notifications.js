/**
 * Notification system for displaying success and error messages
 */

/**
 * Get CSS classes for notification type
 * @param {string} type - The notification type
 * @returns {string} CSS classes
 */
export function getNotificationStyles(type) {
  switch (type) {
    case 'success':
      return 'bg-green-50 text-green-800 border border-green-200';
    case 'error':
      return 'bg-red-50 text-red-800 border border-red-200';
    case 'warning':
      return 'bg-yellow-50 text-yellow-800 border border-yellow-200';
    default:
      return 'bg-blue-50 text-blue-800 border border-blue-200';
  }
}

/**
 * Get icon SVG for notification type
 * @param {string} type - The notification type
 * @returns {string} SVG icon HTML
 */
export function getNotificationIcon(type) {
  switch (type) {
    case 'success':
      return `
        <svg class="w-4 h-4 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
        </svg>
      `;
    case 'error':
      return `
        <svg class="w-4 h-4 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
        </svg>
      `;
    case 'warning':
      return `
        <svg class="w-4 h-4 text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
        </svg>
      `;
    default:
      return `
        <svg class="w-4 h-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
        </svg>
      `;
  }
}

/**
 * Show a notification message
 * @param {string} message - The message to display
 * @param {string} type - The type of notification ('success', 'error', 'info', 'warning')
 * @param {number} duration - Duration in milliseconds before auto-hide (default: 5000)
 */
function showNotification(message, type = 'info', duration = 5000) {
  const container = document.getElementById('notification-container');
  if (!container) {
    console.error('Notification container not found');
    return;
  }

  // Create notification element
  const notification = document.createElement('div');
  notification.className = `
    relative flex items-center px-4 py-3 max-w-sm w-full
    text-sm font-medium rounded-md shadow-lg
    transform transition-all duration-300 ease-in-out
    translate-y-0 opacity-100
    ${getNotificationStyles(type)}
  `
    .trim()
    .replace(/\s+/g, ' ');

  // Create message content
  const messageContent = document.createElement('div');
  messageContent.className = 'flex items-center flex-1';

  // Add icon based on type
  const icon = document.createElement('div');
  icon.className = 'mr-3 flex-shrink-0';
  icon.innerHTML = getNotificationIcon(type);

  const messageText = document.createElement('span');
  messageText.textContent = message;

  messageContent.appendChild(icon);
  messageContent.appendChild(messageText);

  // Create close button
  const closeButton = document.createElement('button');
  closeButton.className = 'ml-3 flex-shrink-0 hover:opacity-70 transition-opacity';
  closeButton.innerHTML = `
    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
    </svg>
  `;
  closeButton.onclick = () => hideNotification(notification);

  notification.appendChild(messageContent);
  notification.appendChild(closeButton);

  // Add to container
  container.appendChild(notification);

  // Animate in
  requestAnimationFrame(() => {
    notification.style.transform = 'translateY(0) scale(1)';
  });

  // Auto-hide after duration
  if (duration > 0) {
    setTimeout(() => {
      hideNotification(notification);
    }, duration);
  }

  return notification;
}

/**
 * Hide a notification with animation
 * @param {HTMLElement} notification - The notification element to hide
 */
function hideNotification(notification) {
  if (!notification || !notification.parentNode) return;

  // Animate out
  notification.style.transform = 'translateY(-100%) scale(0.95)';
  notification.style.opacity = '0';

  // Remove from DOM after animation
  setTimeout(() => {
    if (notification.parentNode) {
      notification.parentNode.removeChild(notification);
    }
  }, 300);
}

/**
 * Show a success notification
 * @param {string} message - Success message
 * @param {number} duration - Duration in milliseconds
 */
function showSuccessNotification(message, duration = 5000) {
  return showNotification(message, 'success', duration);
}

/**
 * Show an error notification
 * @param {string} message - Error message
 * @param {number} duration - Duration in milliseconds (0 = no auto-hide)
 */
function showErrorNotification(message, duration = 8000) {
  return showNotification(message, 'error', duration);
}

/**
 * Show an info notification
 * @param {string} message - Info message
 * @param {number} duration - Duration in milliseconds
 */
function showInfoNotification(message, duration = 5000) {
  return showNotification(message, 'info', duration);
}

/**
 * Show a warning notification
 * @param {string} message - Warning message
 * @param {number} duration - Duration in milliseconds
 */
function showWarningNotification(message, duration = 6000) {
  return showNotification(message, 'warning', duration);
}

// Make functions available globally
window.showNotification = showNotification;
window.showSuccessNotification = showSuccessNotification;
window.showErrorNotification = showErrorNotification;
window.showInfoNotification = showInfoNotification;
window.showWarningNotification = showWarningNotification;
