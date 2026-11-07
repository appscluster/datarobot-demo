import React from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource/source-sans-3/400.css'
import '@fontsource/source-sans-3/600.css'
import '@fontsource/source-sans-3/700.css'
import '@fontsource/jetbrains-mono/400.css'
import 'aos/dist/aos.css'
import './styles.css'
import { Root } from './Root'

createRoot(document.getElementById('root')!).render(<Root />)
