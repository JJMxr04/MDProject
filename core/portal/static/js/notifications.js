document.addEventListener('DOMContentLoaded', function () {
    fetchNotificationsOnLoad();
});

function fetchNotificationsOnLoad() {
    fetch('/web/portal/mail/notifications/')
        .then(response => response.json())
        .then(data => {
            const notifications = data.notifications;
            const notificationDropdown = document.getElementById('notificationDropdown');
            const notificationBadge = document.getElementById('notificationBadge');

            // Clear existing notifications
            notificationDropdown.innerHTML = '';

            if (notifications.length > 0) {
                notifications.forEach(notification => {
                    const li = document.createElement('li');
                    li.classList.add('dropdown-item');
                    li.textContent = notification.message;
                    li.onclick = () => markNotificationAsRead(notification.id, li);
                    notificationDropdown.appendChild(li);
                });

                // Show the notification badge if there are unread notifications
                notificationBadge.style.display = 'block';
            } else {
                const li = document.createElement('li');
                li.classList.add('dropdown-item');
                li.textContent = 'No new notifications';
                notificationDropdown.appendChild(li);
                notificationBadge.style.display = 'none';
            }
        })
        .catch(error => console.error('Error fetching notifications:', error));
}
function getCSRFToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]').value;
}

function markNotificationAsRead(notificationId, listItem) {
    fetch(`/web/portal/mail/notifications/${notificationId}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCSRFToken(),
            'Content-Type': 'application/json',
        },
    })
    .then(response => {
        if (response.ok) {
            listItem.remove();

            const notificationDropdown = document.getElementById('notificationDropdown');
            if (!notificationDropdown.querySelector('.dropdown-item')) {
                const li = document.createElement('li');
                li.classList.add('dropdown-item');
                li.textContent = 'No new notifications';
                notificationDropdown.appendChild(li);

                document.getElementById('notificationBadge').style.display = 'none';
            }
        } else {
            console.error('Failed to mark notification as read');
        }
    })
    .catch(error => console.error('Error marking notification as read:', error));
}
