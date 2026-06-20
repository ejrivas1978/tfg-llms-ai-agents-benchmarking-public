/**
 * Modulo:  llmIcons
 * Ruta:    frontend/src/utils/llmIcons.ts
 *
 * Descripcion:
 *   Re-exporta las URLs de los iconos SVG de cada proveedor LLM para
 *   usarlos como <img src={...}> sin duplicar imports en cada componente.
 *
 * Sprint: Sprint 3
 */

import claude from './claude_anthropic.svg'
import openai from './gpt4o_openai.svg'
import gemini from './gemini_google.svg'
import grok   from './grok_xai.svg'

export const LLM_ICONS: Record<string, string> = { claude, openai, gemini, grok }
