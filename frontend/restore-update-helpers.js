export function chooseRestoreEndpoint({ filename, uploadFile }) {
  if (uploadFile) return '/api/admin/fullbackup/restore-upload';
  if (filename) return '/api/admin/fullbackup/restore';
  return null;
}

export function getUpdateCheckPresentation(data) {
  if (data?.check_ok === false) {
    return {
      badge: '⚠ Check unavailable',
      status: 'Version check unavailable (GitHub API or repo URL issue).',
      variant: 'warning',
    };
  }
  if (data?.up_to_date) {
    return { badge: '✓ Up to date', status: 'Your deployment is up to date.', variant: 'success' };
  }
  return { badge: '⬆ Update available', status: 'A newer version is available on GitHub.', variant: 'info' };
}
