import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

// Avoid React StrictMode double-mount in dev: it disconnects the interview
// WebSocket mid-handshake and can make live transcripts appear then vanish.
createRoot(document.getElementById('root')!).render(<App />)
