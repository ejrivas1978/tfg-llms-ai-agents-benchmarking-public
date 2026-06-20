/**
 * Component/Module: main
 * Path: frontend/src/main.tsx
 *
 * Descripcion:
 *   Punto de entrada de la aplicacion React.
 *   Monta los proveedores globales en orden:
 *     QueryClientProvider  - cache de peticiones al backend (TanStack Query)
 *     RouterProvider       - navegacion entre pantallas (React Router v6)
 *
 * Sprint: Sprint 3
 */
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import './index.css'
import App from './App'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 2,   // 2 minutos antes de marcar como obsoleto
      retry: 1,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  </StrictMode>,
)
