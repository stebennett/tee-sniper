/// <reference types="vite/client" />

declare global {
  interface Window {
    __TSA_CONFIG__?: { apiBaseUrl?: string };
  }
}

export {};
