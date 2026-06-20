/**
 * Modulo:  llmProviders
 * Ruta:    frontend/src/config/llmProviders.ts
 *
 * Descripcion:
 *   Fuente unica de verdad para los metadatos de cada proveedor LLM.
 *   Aplica el principio Open/Closed: anadir un proveedor nuevo solo requiere
 *   agregar una entrada en LLM_PROVIDERS_CONFIG y actualizar LLMProvider en
 *   types/benchmark.ts. Ningun componente necesita modificarse.
 *
 *   Cada entrada declara las capacidades del proveedor (flags booleanos) de
 *   modo que la logica de negocio del frontend (p.ej. que modelos inactivar
 *   en la categoria imagen) se derive de datos, no de strings hardcodeados.
 *
 * Sprint: Sprint 4
 */

import { LLM_ICONS } from '@/utils/llmIcons'
import type { LLMProvider } from '@/types/benchmark'

export interface ProveedorConfig {
  id: LLMProvider
  /** Nombre completo del modelo: "Claude Sonnet 4.6" */
  nombre: string
  /** Nombre corto para graficos y etiquetas: "Claude" */
  nombreCorto: string
  /** Color primario en hex */
  color: string
  /** Fondo semitransparente para tarjetas */
  bg: string
  /** URL del icono SVG */
  icono: string
  /** True si el proveedor puede generar imagenes desde texto */
  puedeGenerarImagenes: boolean
  /** True si el proveedor puede editar una imagen de referencia con su API nativa */
  puedeEditarImagenes: boolean
  /** True si el proveedor acepta imagenes como entrada (vision multimodal) */
  puedeVision: boolean
}

export const LLM_PROVIDERS_CONFIG: Record<LLMProvider, ProveedorConfig> = {
  claude: {
    id:                   'claude',
    nombre:               'Claude Sonnet 4.6',
    nombreCorto:          'Claude',
    color:                '#E8956D',
    bg:                   'rgba(232,149,109,0.10)',
    icono:                LLM_ICONS.claude,
    puedeGenerarImagenes: false,
    puedeEditarImagenes:  false,
    puedeVision:          true,
  },
  openai: {
    id:                   'openai',
    nombre:               'GPT-4o',
    nombreCorto:          'GPT-4o',
    color:                '#10D9A0',
    bg:                   'rgba(16,217,160,0.10)',
    icono:                LLM_ICONS.openai,
    puedeGenerarImagenes: true,
    puedeEditarImagenes:  true,
    puedeVision:          true,
  },
  gemini: {
    id:                   'gemini',
    nombre:               'Gemini 2.5 Flash',
    nombreCorto:          'Gemini',
    color:                '#EF4444',
    bg:                   'rgba(239,68,68,0.10)',
    icono:                LLM_ICONS.gemini,
    puedeGenerarImagenes: true,
    puedeEditarImagenes:  false,
    puedeVision:          true,
  },
  grok: {
    id:                   'grok',
    nombre:               'Grok 4.3',
    nombreCorto:          'Grok',
    color:                '#4DB8FF',
    bg:                   'rgba(77,184,255,0.10)',
    icono:                LLM_ICONS.grok,
    puedeGenerarImagenes: true,
    puedeEditarImagenes:  false,
    puedeVision:          true,
  },
}

/** Lista ordenada de proveedores. El orden determina el layout de la grid de resultados. */
export const PROVEEDORES_LIST: LLMProvider[] = ['claude', 'openai', 'gemini', 'grok']

/** IDs de proveedores que no pueden generar ni editar imagenes (se inactivan en categoria imagen). */
export const PROVEEDORES_SIN_IMAGEN: LLMProvider[] = PROVEEDORES_LIST.filter(
  (id) => !LLM_PROVIDERS_CONFIG[id].puedeGenerarImagenes,
)

/** Acceso rapido al nombre completo de un proveedor. */
export const proveedorNombre = (id: LLMProvider): string =>
  LLM_PROVIDERS_CONFIG[id].nombre

/** Acceso rapido al nombre corto de un proveedor. */
export const proveedorNombreCorto = (id: LLMProvider): string =>
  LLM_PROVIDERS_CONFIG[id].nombreCorto

/** Acceso rapido al color primario de un proveedor. */
export const proveedorColor = (id: LLMProvider): string =>
  LLM_PROVIDERS_CONFIG[id].color

/** Acceso rapido al icono SVG de un proveedor. */
export const proveedorIcono = (id: LLMProvider): string =>
  LLM_PROVIDERS_CONFIG[id].icono
