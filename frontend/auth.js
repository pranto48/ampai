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

    document.querySelectorAll('[data-logout-btn]').forEach((btn) => {
        btn.addEventListener('click', (event) => {
            event.preventDefault();
            logoutAndRedirect();
        });
    });

    return user;
}
