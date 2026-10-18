/**
 * Session windows shared by the admin guard and the sign-in screen.
 *
 * ADMIN_SESSION_MINUTES mirrors the backend's ADMIN_SESSION_MINUTES: the access
 * token for an admin is issued to die exactly when the window closes, and admin
 * tokens are never silently renewed, so this is the real session length.
 *
 * ADMIN_IDLE_MINUTES is enforced in the browser only. The server cannot tell an
 * idle tab from a working one; the guard signs the admin out after this long
 * without input so a shared machine does not sit on a live dashboard.
 */
export const ADMIN_SESSION_MINUTES = 60;
export const ADMIN_IDLE_MINUTES = 30;
