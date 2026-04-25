## 6️⃣ Troubleshooting Dyad Preview

If the Dyad preview shows a blank page or 404 errors:

1. **Verify static files are present** in the Dyad build output:
   - `index.html`, `style.css`, `app.js` should be listed in the build logs.
2. **Check the backend logs** for errors during startup:
   - Look for `Serving static files from ...` – this confirms static serving is active.
3. **Ensure API calls use relative paths**:
   - All fetch requests in `app.js` should be to `/api/...` (no full URLs).
   - Example: `fetch('/api/chat', ...)` not `fetch('https://.../api/chat', ...)`.
4. **Confirm the catch-all route is active**:
   - The backend now serves `index.html` for any unmatched path (e.g., `/dashboard`).
   - This enables client-side routing in the React app.
5. **Rebuild the preview**:
   - Push code changes → Dyad automatically rebuilds the preview.
   - Wait for the "Build succeeded" message before testing.

If problems persist, check the Dyad build logs for specific error messages and share them with support.  

--- That’s all you need to keep a single codebase while Docker uses its own local DB, Dyad preview uses Supabase, and Vercel serves the frontend. Happy coding! 🚀