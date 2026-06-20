/**
 * Modulo:  tokens
 * Ruta:    frontend/src/utils/tokens.ts
 *
 * Descripcion:
 *   Replica de los tokens de diseno de tailwind.config.ts para uso programatico.
 *   Usar cuando Tailwind no puede aplicarse directamente: canvas operations,
 *   props de librerias de graficos (recharts), configuracion de Mermaid, etc.
 *
 *   Para clases CSS normales, usar directamente las clases Tailwind:
 *     bg-surface, text-primary, border-border, etc.
 *
 * Sprint: Sprint 4
 */

export const TOKENS = {
  /* Paleta base */
  bg:         '#080810',
  surface:    '#0F0F1C',
  border:     '#1C1C32',
  text:       '#F4F1FF',
  muted:      '#C0BCDC',
  primary:    '#9D4EDD',
  primaryL:   '#19102B',
  primaryD:   '#7B2FBE',
  primaryGrad: '#6D28D9',  // extremo oscuro del gradiente (p.ej. avatar, botones activos)

  /* Superficies mas profundas (tarjetas interiores, fondos de modal nested) */
  depth:     '#0A0A18',

  /* Textos alternativos */
  textAlt:   '#F5F5F0',   // blanco roto — bordes luminosos y textos sobre fondos oscuros
  textLight: '#EDE9FE',   // lavanda claro — tooltips y etiquetas secundarias

  /* Colores por categoria de benchmark (espejo de tailwind cat1-cat8) */
  cat1: '#A855F7',  // razonamiento
  cat2: '#38BDF8',  // codigo
  cat3: '#FBBF24',  // creativa
  cat4: '#34D399',  // concretas
  cat5: '#F472B6',  // traduccion
  cat6: '#818CF8',  // resumen
  cat7: '#FB923C',  // imagen
  cat8: '#94A3B8',  // libre

  /* Semanticos de estado y UI */
  errorText:   '#F87171',  // rojo suave — errores inline, peor puntuacion
  error:       '#FF0000',  // rojo puro — errores criticos (p.ej. cuota agotada)
  warningText: '#FBBF24',  // amarillo — avisos, tokens restantes
} as const
