import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'
import { ClerkProvider } from '@clerk/react'
import { dark } from '@clerk/themes'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ClerkProvider appearance={{ baseTheme: dark }}>
      <App />
    </ClerkProvider>
  </React.StrictMode>,
)
