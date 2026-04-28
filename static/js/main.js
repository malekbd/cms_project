// Modal management
function openModal(id) {
  document.getElementById(id).classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeModal(id) {
  document.getElementById(id).classList.remove('open');
  document.body.style.overflow = '';
}

// Close modal on overlay click
document.addEventListener('click', (e) => {
  if (e.target.classList.contains('modal-overlay')) {
    e.target.classList.remove('open');
    document.body.style.overflow = '';
  }
});

// Delete confirm
function confirmDelete(pk, name) {
  document.getElementById('deleteMsg').textContent = `Are you sure you want to delete ticket for "${name}"? This cannot be undone.`;
  document.getElementById('deleteForm').action = `/delete/${pk}/`;
  openModal('deleteModal');
}

// Status dropdown toggle
function toggleStatusMenu(btn, pk) {
  const menu = document.getElementById(`menu-${pk}`);
  // Close all other menus
  document.querySelectorAll('.status-menu.show').forEach(m => {
    if (m !== menu) m.classList.remove('show');
  });
  menu.classList.toggle('show');
  event.stopPropagation();
}

// Close status menus on outside click
document.addEventListener('click', () => {
  document.querySelectorAll('.status-menu.show').forEach(m => m.classList.remove('show'));
});

// AJAX status update
function updateStatus(pk, newStatus) {
  fetch(`/status/${pk}/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCookie('csrftoken'),
    },
    body: JSON.stringify({ status: newStatus })
  })
  .then(r => r.json())
  .then(data => {
    if (data.success) {
      // Update badge in UI
      const btn = document.querySelector(`#menu-${pk}`).previousElementSibling;
      const icons = { 'SOLVED': '✅', 'PENDING': '⏳', 'TIME TAKEN': '🕐', 'No Response': '🔕' };
      const classes = { 'SOLVED': 'SOLVED', 'PENDING': 'PENDING', 'TIME TAKEN': 'TIME_TAKEN', 'No Response': 'No_Response' };
      btn.className = `status-badge ${classes[newStatus]}`;
      btn.textContent = `${icons[newStatus]} ${newStatus}`;
      document.getElementById(`menu-${pk}`).classList.remove('show');
      showToast(`Status updated to ${newStatus}`, 'success');
    }
  })
  .catch(() => showToast('Failed to update status', 'error'));
}

// Toast notification
function showToast(msg, type = 'success') {
  const toast = document.createElement('div');
  toast.className = `alert alert-${type}`;
  toast.style.cssText = 'position:fixed; top:20px; right:24px; z-index:9999; min-width:260px; max-width:380px;';
  toast.textContent = (type === 'success' ? '✅ ' : '❌ ') + msg;
  document.body.appendChild(toast);
  setTimeout(() => { toast.style.opacity = '0'; toast.style.transition = '0.4s'; setTimeout(() => toast.remove(), 400); }, 3000);
}

// CSRF cookie helper
function getCookie(name) {
  let value = null;
  document.cookie.split(';').forEach(c => {
    const [k, v] = c.trim().split('=');
    if (k === name) value = decodeURIComponent(v);
  });
  return value;
}

// Keyboard: ESC closes modals
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay.open').forEach(m => {
      m.classList.remove('open');
      document.body.style.overflow = '';
    });
  }
});
