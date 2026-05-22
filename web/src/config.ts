export function apiBaseUrl(): string {
  // Runtime override via /config.js → window.__TSA_CONFIG__.
  // Tests inject http://api.test via vitest globals.
  if (typeof window !== 'undefined' && window.__TSA_CONFIG__?.apiBaseUrl !== undefined) {
    return window.__TSA_CONFIG__.apiBaseUrl;
  }
  return '';
}
