import test from 'node:test';
import assert from 'node:assert/strict';
import { chooseRestoreEndpoint, getUpdateCheckPresentation } from '../restore-update-helpers.js';

test('file-selected branch uses upload endpoint', () => {
  const endpoint = chooseRestoreEndpoint({ filename: 'existing.zip', uploadFile: { name: 'new.zip' } });
  assert.equal(endpoint, '/api/admin/fullbackup/restore-upload');
});

test('dropdown-selected branch uses filename endpoint', () => {
  const endpoint = chooseRestoreEndpoint({ filename: 'saved.zip', uploadFile: null });
  assert.equal(endpoint, '/api/admin/fullbackup/restore');
});

test('update panel warning rendering when check_ok=false', () => {
  const view = getUpdateCheckPresentation({ check_ok: false, up_to_date: false });
  assert.equal(view.variant, 'warning');
  assert.match(view.badge, /Check unavailable/);
  assert.match(view.status, /Version check unavailable/);
});
