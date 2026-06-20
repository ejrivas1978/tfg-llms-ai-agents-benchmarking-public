/**
 * Component/Module: tailwind.config
 * Path: frontend/tailwind.config.ts
 *
 * Descripcion:
 *   Configuracion de Tailwind CSS con los tokens de diseno del TFG.
 *   Los colores de proveedor y categoria estan fijados en el prototipo v1
 *   (docs/prototipos/prototipo_v1.html) y se mapean aqui como tokens
 *   para que esten disponibles en toda la app sin variables CSS duplicadas.
 *
 * Sprint: Sprint 3
 */
import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Paleta base
        bg:           '#080810',
        surface:      '#0F0F1C',
        border:       '#1C1C32',
        text:         '#F4F1FF',
        muted:        '#C0BCDC',
        primary:      '#9D4EDD',
        'primary-l':  '#19102B',
        'primary-d':  '#7B2FBE',
        'primary-g':  '#6D28D9',  // extremo oscuro del gradiente

        // Superficies y textos adicionales
        depth:        '#0A0A18',  // tarjetas nested, fondos de modal interior
        'text-alt':   '#F5F5F0',  // blanco roto — bordes luminosos y textos sobre oscuro
        'text-light': '#EDE9FE',  // lavanda claro — tooltips y etiquetas

        // Colores por proveedor LLM
        claude:  '#E8956D',
        openai:  '#10D9A0',
        gemini:  '#EF4444',
        grok:    '#4DB8FF',

        // Colores por categoria de benchmark
        cat1: '#A855F7',
        cat2: '#38BDF8',
        cat3: '#FBBF24',
        cat4: '#34D399',
        cat5: '#F472B6',
        cat6: '#818CF8',
        cat7: '#FB923C',
        cat8: '#94A3B8',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      borderRadius: {
        card: '14px',
      },
      boxShadow: {
        card: '0 2px 16px rgba(0,0,0,.45)',
        'card-lg': '0 8px 40px rgba(0,0,0,.65)',
      },
    },
  },
  plugins: [],
} satisfies Config
