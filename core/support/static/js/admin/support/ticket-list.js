
    document.addEventListener('DOMContentLoaded', function() {
        const listViewBtn = document.getElementById('list-view-btn');
        const kanbanViewBtn = document.getElementById('kanban-view-btn');
        const listView = document.getElementById('list-view');
        const kanbanView = document.getElementById('kanban-view');

        listViewBtn.addEventListener('click', function() {
            listView.classList.add('active');
            kanbanView.classList.remove('active');
            listViewBtn.classList.add('active');
            kanbanViewBtn.classList.remove('active');
        });

        kanbanViewBtn.addEventListener('click', function() {
            kanbanView.classList.add('active');
            listView.classList.remove('active');
            kanbanViewBtn.classList.add('active');
            listViewBtn.classList.remove('active');
        });

        // Initialize drag-and-drop for Kanban columns
        document.querySelectorAll('.kanban-column-content').forEach(function(column) {
            new Sortable(column, {
                group: 'kanban',
                animation: 200,
                onEnd: function(evt) {
                    const ticketId = evt.item.dataset.ticketId;
                    const newStatus = evt.to.parentNode.dataset.status;

                    // Update ticket status using an AJAX request
                    fetch('{% url "core-admin:update_ticket_status" %}', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': '{{ csrf_token }}'
                        },
                        body: JSON.stringify({ticket_id: ticketId, status_id: newStatus})
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            console.log('Ticket updated successfully');
                        } else {
                            console.error('Failed to update ticket');
                        }
                    });
                }
            });
        });
    });
