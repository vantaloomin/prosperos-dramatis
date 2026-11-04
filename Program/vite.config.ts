import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Port 5207 and backend 8815 keep Dramatis clear of the other Prospero apps (Adventure is 5197 and 8805), so they
// can all run at once.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5207,
    strictPort: true,
    proxy: { '/api': 'http://127.0.0.1:8815' },
  },
})
