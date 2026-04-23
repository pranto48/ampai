# Authentication Environment Configuration

Ampai uses cookie-based JWT sessions with role-based access control (RBAC).

## Required variables

- `JWT_SECRET` **(required)**: Secret used to sign JWT access tokens.
  - Use a long, random value in production.
- `JWT_EXPIRY_MINUTES` *(optional, default: `60`)*: Access token TTL in minutes.

## Built-in user accounts

Ampai creates two accounts from environment variables at startup:

- Admin account:
  - `ADMIN_USERNAME` (default: `admin`)
  - `ADMIN_PASSWORD` (default: `admin123`)
- Standard user account:
  - `USER_USERNAME` (default: `user`)
  - `USER_PASSWORD` (default: `user123`)

## Example (`docker-compose.yml`)

```yaml
environment:
  - JWT_SECRET=change-this-in-production
  - JWT_EXPIRY_MINUTES=60
  - ADMIN_USERNAME=admin
  - ADMIN_PASSWORD=admin123
  - USER_USERNAME=user
  - USER_PASSWORD=user123
```

## Notes

- Access tokens are sent as HTTP-only cookies (`access_token`).
- Admin-only API routes enforce the `admin` role.
- Authenticated non-admin users are assigned the `user` role.
