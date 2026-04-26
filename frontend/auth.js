async function fetchCurrentUser() {
    const token = localStorage.getItem('ampai_token') || '';
    const headers = token ? { Authorization: `Bearer ${token}` } : {};
    const response = await fetch('/api/auth/me', { headers });
    if (!response.ok) {
        return null;
    }
    return response.json();
}

async function logoutAndRedirect() {
    const token = localStorage.getItem('ampai_token') || '';
    const headers = token ? { Authorization: `Bearer ${token}` } : {};
    await fetch('/api/auth/logout', { method: 'POST', headers });
    localStorage.removeItem('ampai_token');
    localStorage.removeItem('ampai_role');
    localStorage.removeItem('ampai_username');
    window.location.href = '/index.html';
}

async function enforceAuth({ requiredRole = null, redirectTo = '/index.html' } = {}) {
    const user = await fetchCurrentUser();
    if (!user) {
        window.location.href = redirectTo;
        return null;
    }

    if (requiredRole && user.role !== requiredRole) {
        window.location.href = '/index.html';
        return null;
    }

    const roleBadge = document.getElementById('auth-role');
    if (roleBadge) {
        roleBadge.textContent = user.role.toUpperCase();
    }

    const userLabel = document.getElementById('auth-user');
    if (userLabel) {
        userLabel.textContent = user.username;
    }

    document.querySelectorAll('[data-admin-link]').forEach((link) => {
        link.style.display = user.role === 'admin' ? '' : 'none';
    });

    document.querySelectorAll('[data-logout-btn]').forEach((btn) => {
        btn.addEventListener('click', (event) => {
            event.preventDefault();
            logoutAndRedirect();
        });
    });

    const menuBtn = document.querySelector('[data-user-menu-btn]');
    const menuPanel = document.querySelector('[data-user-menu-panel]');
    if (menuBtn && menuPanel) {
        menuBtn.addEventListener('click', (event) => {
            event.preventDefault();
            menuPanel.classList.toggle('open');
        });

        document.addEventListener('click', (event) => {
            if (!menuPanel.contains(event.target) && !menuBtn.contains(event.target)) {
                menuPanel.classList.remove('open');
            }
        });
    }

    return user;
}
