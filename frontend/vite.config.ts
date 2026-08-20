import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Matches the backend's default settings.frontend_url (see app/core/config.py),
    // which CORS is locked to.
    port: 3000,
  },
})
