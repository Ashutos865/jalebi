import { defineConfig } from 'wxt';
import tailwindcss from '@tailwindcss/vite';

// WXT config — https://wxt.dev
// Generates the MV3 manifest from these fields + the entrypoints/ directory.
export default defineConfig({
  modules: ['@wxt-dev/module-react'],
  srcDir: '.',
  vite: () => ({
    plugins: [tailwindcss()],
  }),
  manifest: {
    // Pins a permanent extension ID (bheipmanmllnpjmgnhikfpcbcdnopdjo)
    // so the Google OAuth client stays valid across reloads/moves.
    key: 'MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAtuGmGBCD0HlyMfN/95jeOR0RGzotQpr9nw8Rt4BkRyJi9oADbshYovaTUfL7PELobzNtOHWzkVR8lwAt7LdUt0Eit9zY44Pn7sIHLSlTbI87AfYRAtSiFcQgDbTqeKeZiJg2NBeUyrDzv2lA2DbnA7ohQxC55AVszuDvScl8YYFMwbRzzgg2UiaMx1DRyXrCrqLBDXQraP/VIam0duI0TG6WkyYwDaq5Zn9zinnzFy7u/NjHsHZhYqaELf3Xf5QVrhsAFHmMU5TaQSbHpn601c1hraMYwN2UQm5Lia8pXPYEPh/r29tQUDDo+Y2mU2cGcdC1l+dsTAuK+gGRzVgOQwIDAQAB',
    name: 'Jalebi — Editorial QA',
    description:
      'Evaluate Google Docs against TIES editorial standards before publication.',
    permissions: ['sidePanel', 'activeTab', 'tabs', 'storage', 'identity'],
    // Google Docs (for extraction) + Google APIs (highlight/comment) + localhost.
    host_permissions: [
      'https://docs.google.com/*',
      'https://*.googleusercontent.com/*', // Docs export can redirect here
      'https://docs.googleapis.com/*', // Docs API (highlights)
      'https://www.googleapis.com/*', // Drive API (comments)
      'http://localhost/*',
      'http://127.0.0.1/*',
    ],
    optional_host_permissions: ['https://*/*', 'http://*/*'],
    // Google OAuth for in-doc highlights + comments (chrome.identity). Create a
    // "Chrome Extension" OAuth client and set GOOGLE_OAUTH_CLIENT_ID before building.
    oauth2: {
      client_id:
        process.env.GOOGLE_OAUTH_CLIENT_ID ||
        '531691733397-ok54krc78fmd2kp9093g1b1i8rhvn5g9.apps.googleusercontent.com',
      scopes: [
        'https://www.googleapis.com/auth/documents',
        'https://www.googleapis.com/auth/drive',
      ],
    },
    action: {
      default_title: 'Open Jalebi',
    },
    // The side panel opens on the toolbar icon click (set in background.ts).
    side_panel: {
      default_path: 'sidepanel.html',
    },
  },
});
