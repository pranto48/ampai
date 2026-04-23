async function fetchCurrentUser() {
    const response = await fetch('/api/auth/me');
    if (!response.ok) {
        return null;
    }
    return response.json();
}

async function logoutAndRedirect() {
    await fetch('/api/auth/logout', { method: 'POST' });
    window.location.href = '/login.html';
}

async function enforceAuth({ requiredRole = null, redirectTo = '/login.html' } = {}) {
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
