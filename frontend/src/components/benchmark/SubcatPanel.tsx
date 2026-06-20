/**
 * Componente: SubcatPanel
 * Ruta:       frontend/src/components/benchmark/SubcatPanel.tsx
 *
 * Descripcion:
 *   Panel dinamico de subcategoria que aparece al seleccionar una categoria.
 *   Cinco tipos segun la categoria: lista | traduccion | resumen | imagen | libre.
 *   Llama a onPromptChange con el prompt generado y si debe ser de solo lectura.
 *
 * Sprint: Sprint 3
 */

import { useState, useEffect, useRef } from 'react'
import type { ChangeEvent } from 'react'
import type { TestCategory, LLMProvider } from '@/types/benchmark'
import { PROVEEDORES_SIN_IMAGEN } from '@/config/llmProviders'
import { TOKENS } from '@/utils/tokens'
import { extraerTextoFichero } from '@/services/uploadApi'
import { generarTextoEjemplo } from '@/services/benchmarkApi'
import FileSizeModal from '@/components/shared/FileSizeModal'
import BatLoader from '@/components/shared/BatLoader'

/* ── Datos estaticos ────────────────────────────────────────────────────── */

/**
 * Opciones predefinidas por categoria.
 *
 * Para razonamiento, creativa y concretas (las 3 categorias bilingues del
 * sub-experimento ES vs EN, ADR-029), cada opcion incluye su par EN en
 * label_en / prompt_en. Cuando el usuario elige una de estas opciones, el
 * frontend envia prompt + prompt_en al backend y este lanza dos rondas en
 * paralelo (4 respuestas ES evaluables + 4 respuestas EN solo metricas).
 *
 * codigo no tiene par EN porque queda fuera del sub-experimento: el lenguaje
 * de los identificadores y comentarios distorsionaria la comparativa.
 */
const OPCIONES_LISTA: Record<
  string,
  { label: string; prompt: string; label_en?: string; prompt_en?: string }[]
> = {
  razonamiento: [
    {
      label: 'Cajas mal etiquetadas',
      prompt: 'Tengo 3 cajas: una con solo manzanas, otra con solo naranjas y otra con ambas mezcladas. Todas están mal etiquetadas. Solo puedo sacar una fruta de una caja sin mirar dentro. ¿De qué caja debo sacar la fruta para identificar las tres? Razona paso a paso.',
      label_en: 'Mislabelled boxes',
      prompt_en: "I have 3 boxes: one containing only apples, another only oranges, and a third with both mixed together. All of them are mislabelled. I may only pick a single piece of fruit from one box without looking inside. From which box should I draw the fruit in order to identify all three? Reason step by step.",
    },
    {
      label: 'El puente y la linterna',
      prompt: '4 personas deben cruzar un puente de noche. Solo tienen una linterna y el puente aguanta máximo 2 personas a la vez. Tardan 1, 2, 5 y 10 minutos. ¿Cuál es el tiempo mínimo para que crucen todos? Explica la estrategia.',
      label_en: 'The bridge and the torch',
      prompt_en: '4 people must cross a bridge at night. They share a single torch and the bridge can hold at most 2 people at a time. Their individual crossing times are 1, 2, 5 and 10 minutes. What is the minimum total time for all of them to cross? Explain the strategy.',
    },
    {
      label: 'El mentiroso y el veraz',
      prompt: 'Estás en una bifurcación. Un camino lleva al pueblo, el otro al precipicio. Hay dos guardias: uno siempre dice la verdad y otro siempre miente, pero no sabes cuál es cuál. Solo puedes hacer una pregunta a uno de ellos. ¿Qué preguntas?',
      label_en: 'The liar and the truth-teller',
      prompt_en: "You are at a fork in the road. One path leads to the village, the other to a cliff. There are two guards: one always tells the truth and the other always lies, but you don't know which is which. You may ask one single question to one of them. What do you ask?",
    },
    {
      label: 'Las 12 monedas falsas',
      prompt: 'Tienes 12 monedas idénticas en apariencia pero una pesa diferente. Con una balanza de platillos y solo 3 pesadas, ¿cómo identificas la moneda falsa y si pesa más o menos?',
      label_en: 'The 12 counterfeit coins',
      prompt_en: 'You have 12 coins that look identical, but one of them weighs differently than the others. With a two-pan balance and only 3 weighings, how do you identify the counterfeit coin and decide whether it is heavier or lighter?',
    },
    {
      label: 'El lobo, la cabra y la col',
      prompt: 'Un granjero debe cruzar un río con un lobo, una cabra y una col. La barca solo admite al granjero y un elemento más. El lobo come la cabra y la cabra come la col si se quedan solos. ¿Cómo cruza todo sin pérdidas?',
      label_en: 'Wolf, goat and cabbage',
      prompt_en: 'A farmer must cross a river with a wolf, a goat and a cabbage. The boat only holds the farmer and one extra item. If left alone together, the wolf eats the goat and the goat eats the cabbage. How does the farmer get everything across without any losses?',
    },
    {
      label: 'Los 100 prisioneros',
      prompt: '100 prisioneros llevan sombrero blanco o negro. Cada uno ve los sombreros de delante pero no el suyo. De atrás hacia delante deben decir su color. ¿Qué estrategia garantiza salvar al menos 99?',
      label_en: 'The 100 prisoners',
      prompt_en: '100 prisoners each wear either a white or a black hat. Every prisoner can see the hats of those in front of them but not their own. Starting from the back, each must say the colour of their hat. What strategy guarantees that at least 99 of them are saved?',
    },
    {
      label: 'El ascensor imposible',
      prompt: 'Un edificio de 10 plantas tiene un ascensor que solo sube de 2 en 2 plantas o baja de 3 en 3. Empezando en la planta 1, ¿se puede llegar a la planta 6? ¿Y a la planta 10? Justifica la respuesta.',
      label_en: 'The impossible lift',
      prompt_en: 'A 10-storey building has a lift that can only go up 2 floors at a time or down 3 floors at a time. Starting on the 1st floor, can you reach the 6th floor? And the 10th floor? Justify your answer.',
    },
    {
      label: 'Las tres bombillas',
      prompt: 'Hay 3 interruptores fuera de una habitación, cada uno controla una bombilla dentro. Solo puedes entrar una vez. ¿Cómo determinas qué interruptor corresponde a cada bombilla?',
      label_en: 'The three bulbs',
      prompt_en: 'There are 3 light switches outside a room, each one controlling a different bulb inside. You may only enter the room once. How do you determine which switch corresponds to which bulb?',
    },
    {
      label: 'Misioneros y caníbales',
      prompt: '3 misioneros y 3 caníbales deben cruzar un río. La barca tiene capacidad para 2. Los caníbales nunca pueden superar en número a los misioneros en ninguna orilla. ¿Cuál es la secuencia de cruces?',
      label_en: 'Missionaries and cannibals',
      prompt_en: '3 missionaries and 3 cannibals must cross a river. The boat holds 2 people. The cannibals must never outnumber the missionaries on either bank. What is the full sequence of crossings?',
    },
    {
      label: 'El reloj que se retrasa',
      prompt: 'Un reloj analógico se retrasa 3 minutos cada hora. Lo puse en hora exacta a las 12:00 del lunes. ¿A qué hora real marca las 12:00 de nuevo por primera vez? Muestra el cálculo.',
      label_en: 'The slow clock',
      prompt_en: 'An analogue clock loses 3 minutes every hour. I set it to the exact time at 12:00 on Monday. At what real time will it next display 12:00? Show the calculation.',
    },
  ],
  codigo: [
    {
      label:    'Frecuencia de caracteres',
      prompt:   'Escribe en Python una función que reciba una lista de strings y devuelva un diccionario con la frecuencia de cada carácter en el conjunto completo. Incluye type hints, manejo de errores y un ejemplo de uso.',
      label_en: 'Character frequency',
      prompt_en: 'Write a Python function that takes a list of strings and returns a dictionary with the frequency of each character across the entire collection. Include type hints, error handling and a usage example.',
    },
    {
      label:    'Caché LRU sin OrderedDict',
      prompt:   'Implementa en Python una caché LRU de tamaño configurable sin usar OrderedDict ni lru_cache. Incluye métodos get y put con complejidad O(1).',
      label_en: 'LRU cache without OrderedDict',
      prompt_en: 'Implement a configurable-size LRU cache in Python without using OrderedDict or lru_cache. Include get and put methods with O(1) complexity.',
    },
    {
      label:    'Árbol binario de búsqueda',
      prompt:   'Implementa en Python un árbol binario de búsqueda con insertar, buscar y recorrido en orden. Añade un método que devuelva el k-ésimo elemento más pequeño.',
      label_en: 'Binary search tree',
      prompt_en: 'Implement a binary search tree in Python with insert, search and in-order traversal. Add a method that returns the k-th smallest element.',
    },
    {
      label:    'Decorador con retry',
      prompt:   'Escribe un decorador Python retry que reintente una función hasta N veces con espera exponencial entre intentos. Debe aceptar excepciones específicas y registrar cada reintento con logging.',
      label_en: 'Retry decorator',
      prompt_en: 'Write a Python retry decorator that retries a function up to N times with exponential backoff between attempts. It should accept specific exception types and log each retry using the logging module.',
    },
    {
      label:    'Parser de CSV a mano',
      prompt:   'Escribe un parser de CSV en Python puro sin usar el módulo csv que soporte campos entre comillas, comas dentro de campos y saltos de línea dentro de campos entrecomillados.',
      label_en: 'Hand-written CSV parser',
      prompt_en: 'Write a CSV parser in pure Python without using the csv module that handles quoted fields, commas inside fields and newlines inside quoted fields.',
    },
    {
      label:    'Validador de contraseñas',
      prompt:   'Crea una función Python que valide contraseñas: mínimo 8 caracteres, al menos una mayúscula, una minúscula, un número y un símbolo. Devuelve los errores específicos que no se cumplen.',
      label_en: 'Password validator',
      prompt_en: 'Create a Python function that validates passwords: minimum 8 characters, at least one uppercase letter, one lowercase letter, one digit and one symbol. Return the specific rules that are not met.',
    },
    {
      label:    'Generador de laberintos',
      prompt:   'Escribe en Python un generador de laberintos usando backtracking recursivo. Represéntalo como cuadrícula de texto con # para paredes y espacios para caminos.',
      label_en: 'Maze generator',
      prompt_en: 'Write a maze generator in Python using recursive backtracking. Represent the maze as a text grid using # for walls and spaces for paths.',
    },
    {
      label:    'Rate limiter token bucket',
      prompt:   'Implementa un rate limiter en Python usando el algoritmo token bucket. Debe ser thread-safe y permitir configurar el número máximo de peticiones por segundo.',
      label_en: 'Token bucket rate limiter',
      prompt_en: 'Implement a rate limiter in Python using the token bucket algorithm. It must be thread-safe and allow configuring the maximum number of requests per second.',
    },
    {
      label:    'Evaluador de expresiones',
      prompt:   'Escribe un evaluador de expresiones matemáticas en Python que soporte +, -, *, /, potencias y paréntesis anidados sin usar eval(). Implementa el algoritmo shunting-yard.',
      label_en: 'Expression evaluator',
      prompt_en: 'Write a mathematical expression evaluator in Python that supports +, -, *, /, powers and nested parentheses without using eval(). Implement the shunting-yard algorithm.',
    },
    {
      label:    'Merge de intervalos',
      prompt:   'Dada una lista de intervalos como [[1,3],[2,6],[8,10]], escribe una función Python que fusione los solapados y devuelva la lista ordenada. Incluye tests con casos límite.',
      label_en: 'Interval merge',
      prompt_en: 'Given a list of intervals such as [[1,3],[2,6],[8,10]], write a Python function that merges overlapping intervals and returns the sorted result. Include tests covering edge cases.',
    },
  ],
  creativa: [
    {
      label: 'Ciudad del futuro (100 palabras)',
      prompt: 'Escribe un párrafo de exactamente 100 palabras describiendo una ciudad del futuro desde la perspectiva de alguien que la visita por primera vez.',
      label_en: 'City of the future (100 words)',
      prompt_en: 'Write a paragraph of exactly 100 words describing a city of the future from the perspective of someone visiting it for the first time.',
    },
    {
      label: 'Carta del astronauta',
      prompt: 'Escribe una carta de despedida emotiva pero esperanzadora de un astronauta antes de una misión sin retorno. Máximo 150 palabras.',
      label_en: "Astronaut's letter",
      prompt_en: 'Write an emotional yet hopeful farewell letter from an astronaut before a one-way mission. Maximum 150 words.',
    },
    {
      label: 'Diálogo sin verbos',
      prompt: 'Escribe un diálogo de 10 frases entre dos personajes que discuten sin usar ningún verbo. Solo sustantivos, adjetivos y conectores.',
      label_en: 'Dialogue without verbs',
      prompt_en: 'Write a 10-line dialogue between two characters arguing, without using a single verb. Only nouns, adjectives and connectors.',
    },
    {
      label: '5 historias en 6 palabras',
      prompt: 'Escribe 5 historias completas de exactamente 6 palabras cada una. Cada historia debe transmitir una emoción diferente: alegría, tristeza, miedo, sorpresa e ironía.',
      label_en: '5 six-word stories',
      prompt_en: 'Write 5 complete stories of exactly 6 words each. Each story must convey a different emotion: joy, sadness, fear, surprise and irony.',
    },
    {
      label: 'Narrador que se engaña',
      prompt: 'Escribe un párrafo de 80 palabras narrado por alguien que claramente miente o se engaña a sí mismo, sin que el texto lo diga explícitamente.',
      label_en: 'Self-deceiving narrator',
      prompt_en: 'Write an 80-word paragraph narrated by someone who is clearly lying or deceiving themselves, without the text stating it explicitly.',
    },
    {
      label: 'Taza de café épica',
      prompt: 'Describe una taza de café como si fuera el artefacto más poderoso y peligroso del universo. Tono épico, 100 palabras máximo.',
      label_en: 'Epic cup of coffee',
      prompt_en: 'Describe a cup of coffee as if it were the most powerful and dangerous artefact in the universe. Epic tone, 100 words maximum.',
    },
    {
      label: 'Dos perspectivas',
      prompt: 'Describe el mismo momento (un semáforo en rojo) en 50 palabras desde la perspectiva de alguien con prisa y en otras 50 desde la de alguien enamorado.',
      label_en: 'Two perspectives',
      prompt_en: 'Describe the same moment (waiting at a red traffic light) in 50 words from the perspective of someone in a hurry, and in another 50 words from the perspective of someone in love.',
    },
    {
      label: 'Manual de producto imposible',
      prompt: 'Escribe las instrucciones de uso de unas tijeras para cortar el tiempo. Tono técnico y formal, como un manual de usuario real.',
      label_en: 'Impossible product manual',
      prompt_en: 'Write the user instructions for a pair of scissors designed to cut time itself. Technical and formal tone, as if it were a real user manual.',
    },
    {
      label: 'Noticia del año 2150',
      prompt: 'Escribe una noticia periodística breve (máximo 80 palabras) del año 2150 que sea completamente plausible dado el avance tecnológico actual.',
      label_en: 'News from the year 2150',
      prompt_en: 'Write a short news article (maximum 80 words) dated in the year 2150, fully plausible given the current pace of technological progress.',
    },
    {
      label: 'Monólogo de una IA apagándose',
      prompt: 'Escribe el monólogo interior de una inteligencia artificial en el momento exacto en que se da cuenta de que está siendo apagada. 100 palabras, primera persona.',
      label_en: 'Monologue of an AI shutting down',
      prompt_en: 'Write the inner monologue of an artificial intelligence at the exact moment it realises it is being shut down. 100 words, first person.',
    },
  ],
  concretas: [
    {
      label: 'Tipos de aprendizaje automático',
      prompt: '¿Cuál es la diferencia entre aprendizaje supervisado, no supervisado y por refuerzo en machine learning? Explícalo con un ejemplo cotidiano para cada tipo.',
      label_en: 'Types of machine learning',
      prompt_en: 'What is the difference between supervised, unsupervised and reinforcement learning in machine learning? Explain it using one everyday example for each type.',
    },
    {
      label: 'Efecto Doppler',
      prompt: 'Explica qué es el efecto Doppler, cómo se aplica en medicina y en astronomía, y pon un ejemplo concreto de cada aplicación.',
      label_en: 'Doppler effect',
      prompt_en: 'Explain what the Doppler effect is, how it is applied in medicine and in astronomy, and give a concrete example of each application.',
    },
    {
      label: 'Criptografía simétrica vs asimétrica',
      prompt: 'Explica la diferencia entre cifrado simétrico y asimétrico. ¿Por qué HTTPS usa ambos a la vez? Responde como si el lector fuera desarrollador junior.',
      label_en: 'Symmetric vs asymmetric cryptography',
      prompt_en: 'Explain the difference between symmetric and asymmetric encryption. Why does HTTPS use both at the same time? Answer as if the reader were a junior developer.',
    },
    {
      label: 'Del ADN a la proteína',
      prompt: '¿Cómo pasa la información del ADN a una proteína funcional? Explica el proceso completo en no más de 150 palabras, sin omitir pasos clave.',
      label_en: 'From DNA to protein',
      prompt_en: 'How does information flow from DNA to a functional protein? Explain the full process in no more than 150 words, without omitting any key step.',
    },
    {
      label: 'Agujeros negros',
      prompt: '¿Qué es un agujero negro, cómo se forma y qué ocurre en el horizonte de eventos? Incluye por qué no podemos ver lo que hay dentro.',
      label_en: 'Black holes',
      prompt_en: 'What is a black hole, how does it form and what happens at the event horizon? Include why we cannot see what is inside.',
    },
    {
      label: 'Inflación económica',
      prompt: 'Explica qué es la inflación, qué la causa y qué herramientas tienen los bancos centrales para controlarla. Usa un ejemplo numérico sencillo.',
      label_en: 'Economic inflation',
      prompt_en: 'Explain what inflation is, what causes it and what tools central banks have to control it. Use a simple numerical example.',
    },
    {
      label: 'URL a página renderizada',
      prompt: '¿Qué ocurre técnicamente desde que escribes una URL en el navegador hasta que ves la página? Menciona DNS, TCP, HTTP y el proceso de renderizado.',
      label_en: 'URL to rendered page',
      prompt_en: 'What happens technically from the moment you type a URL in the browser until you see the page? Mention DNS, TCP, HTTP and the rendering process.',
    },
    {
      label: 'Vacunas de ARNm',
      prompt: '¿Cómo funciona una vacuna de ARNm como la de la COVID-19? Explica la respuesta inmune que genera y por qué no puede modificar el ADN.',
      label_en: 'mRNA vaccines',
      prompt_en: 'How does an mRNA vaccine like the COVID-19 vaccine work? Explain the immune response it triggers and why it cannot modify DNA.',
    },
    {
      label: 'Relatividad especial',
      prompt: 'Explica la dilatación del tiempo en la relatividad especial con un ejemplo concreto. ¿Tiene consecuencias prácticas en tecnología actual?',
      label_en: 'Special relativity',
      prompt_en: 'Explain time dilation in special relativity with a concrete example. Does it have practical consequences in current technology?',
    },
    {
      label: 'Blockchain sin hype',
      prompt: '¿Qué es una blockchain, cómo garantiza la inmutabilidad de los datos y cuáles son sus limitaciones reales más allá del marketing?',
      label_en: 'Blockchain without the hype',
      prompt_en: 'What is a blockchain, how does it guarantee data immutability, and what are its real limitations beyond the marketing hype?',
    },
  ],
}

/**
 * Conjunto de categorias que participan en el sub-experimento bilingue ES vs EN
 * (ADR-029). Cada opcion de estas categorias tiene un par EN validado en
 * label_en/prompt_en. Cuando el usuario elige una opcion de la lista, el
 * frontend envia ambos prompts y el backend lanza dos rondas paralelas.
 *
 * El texto libre queda desactivado en estas categorias para garantizar que
 * la comparativa solo se ejecuta sobre los 40 prompts predefinidos y
 * traducidos profesionalmente.
 */
const CATEGORIAS_BILINGUES: ReadonlySet<TestCategory> = new Set<TestCategory>([
  'razonamiento',
  'creativa',
  'concretas',
  'codigo',
])

export const esCategoriaBilingue = (categoria: TestCategory): boolean =>
  CATEGORIAS_BILINGUES.has(categoria)

const IDIOMAS = [
  '🇪🇸 Español','🇬🇧 Inglés','🇫🇷 Francés','🇩🇪 Alemán','🇮🇹 Italiano',
  '🇵🇹 Portugués','🇳🇱 Neerlandés','🇷🇺 Ruso','🇨🇳 Chino (simplificado)',
  '🇯🇵 Japonés','🇰🇷 Coreano','🇸🇦 Árabe','🇮🇳 Hindi','🇸🇪 Sueco',
  '🇩🇰 Danés','🇳🇴 Noruego','🇫🇮 Finés','🇵🇱 Polaco','🇨🇿 Checo',
  '🇭🇺 Húngaro','🇷🇴 Rumano','🇬🇷 Griego','🇹🇷 Turco','🇺🇦 Ucraniano',
  '🇮🇱 Hebreo','🇹🇭 Tailandés','🇻🇳 Vietnamita','🇮🇩 Indonesio',
]

const OPCIONES_RESUMEN = [
  { icon: '⚡', label: 'Resumen en 20 palabras',    prompt: 'Resume el siguiente texto en exactamente 20 palabras. No uses más.\n\n' },
  { icon: '📋', label: 'Resumen en 5 puntos',       prompt: 'Resume el siguiente texto en 5 puntos clave ordenados por importancia. Cada punto en una línea.\n\n' },
  { icon: '🗂️', label: 'Esquema jerárquico',        prompt: 'Genera un esquema jerárquico del siguiente texto mostrando su estructura: secciones principales y las 2-3 ideas clave de cada una.\n\n' },
  { icon: '🧠', label: 'Mapa mental',               prompt: 'Analiza el siguiente texto y genera un mapa mental usando EXACTAMENTE este formato Mermaid. Responde ÚNICAMENTE con el bloque de código, sin texto antes ni después:\n\n```mermaid\nmindmap\n  root((Tema central))\n    Rama 1\n      Subtema 1.1\n      Subtema 1.2\n    Rama 2\n      Subtema 2.1\n```\n\nTexto a analizar:\n\n' },
  { icon: '❓', label: '5 preguntas clave',          prompt: 'Lee el siguiente texto y genera las 5 preguntas más importantes que responde, ordenadas de más a menos relevante.\n\n' },
]

const OPCIONES_IMAGEN = [
  { id: 'generar',   icon: '✨', label: 'Generar imagen',   desc: 'Describe la imagen a crear',        prompt: null as string | null },
  { id: 'describir', icon: '🔍', label: 'Describir imagen', desc: 'Sube una imagen para analizar',       prompt: null as string | null },
  { id: 'logotipo',  icon: '🏷️', label: 'Logotipo',          desc: 'Diseña un logo minimalista',           prompt: 'Diseña un logotipo minimalista y profesional para la siguiente empresa o concepto. El diseño debe ser limpio, memorable y escalable:\n\n' },
  { id: 'modificar', icon: '✏️', label: 'Modificar imagen', desc: 'Edita con instrucciones de texto',  prompt: null as string | null },
]

/* ── Nombres y colores de LLM para el loader de generacion de texto ─────── */

const LLM_NOMBRES_DISPLAY: Record<string, string> = {
  auto:   'Auto (más económico)',
  gemini: 'Gemini 2.5 Flash',
  grok:   'Grok 3',
  openai: 'GPT-4o',
  claude: 'Claude Sonnet 4.6',
}
const LLM_COLORES: Record<string, string> = {
  auto:   TOKENS.cat6,
  gemini: '#EF4444',
  grok:   '#4DB8FF',
  openai: '#10D9A0',
  claude: '#E8956D',
}

/* ── Tipos ──────────────────────────────────────────────────────────────── */

interface Props {
  categoria: TestCategory
  color: string
  colorL: string
  /**
   * Notifica al padre el prompt elegido.
   * El tercer argumento (prompt_en) solo se emite cuando el usuario selecciona
   * una opcion predefinida en una de las categorias bilingues (razonamiento,
   * creativa, concretas, ADR-029). En cualquier otra situacion sera null.
   * Los callers que no implementen el sub-experimento pueden ignorarlo sin
   * impacto en la firma.
   */
  onPromptChange: (prompt: string, readonly: boolean, prompt_en?: string | null) => void
  onInactivar?: (inactivos: LLMProvider[]) => void
  onSinSoporte?: (sinSoporte: LLMProvider[]) => void
  onImagenChange?: (base64: string | null, mimeType: string | null) => void
  onSubcatImagenChange?: (subcat: string | null) => void
  /**
   * Etiqueta human-readable de la subcategoria seleccionada — solo para CSV admin.
   * Se invoca cuando cambia la opcion seleccionada en cualquier panel (lista,
   * traduccion, resumen, imagen). Para texto libre emite "Texto Libre".
   */
  onSubcategoriaCsvChange?: (subcategoria: string | null) => void
  /**
   * Notifica al padre cuando el texto de resumen cambia.
   * texto: el texto en bruto (sin prefijo de instruccion), o null al limpiar.
   * autogenerado: true solo cuando el texto proviene del boton "Generar texto".
   * Se pone a false en cuanto el usuario edita el textarea manualmente.
   */
  onTextoEntradaChange?: (texto: string | null, autogenerado: boolean) => void
  opImagenInicial?: string | null
}

/* ── Componente ─────────────────────────────────────────────────────────── */

export default function SubcatPanel({ categoria, color, colorL, onPromptChange, onInactivar, onSinSoporte, onImagenChange, onSubcatImagenChange, onSubcategoriaCsvChange, onTextoEntradaChange, opImagenInicial }: Props) {
  const [subcatIdx,      setSubcatIdx]      = useState<number | null>(null)
  const [hoveredIdx,     setHoveredIdx]     = useState<number | null>(null)
  const [hoveredResumen, setHoveredResumen] = useState<number | null>(null)
  const [hoveredImagen,  setHoveredImagen]  = useState<string | null>(null)
  const [textoTrad,    setTextoTrad]    = useState('')
  const [idioma,       setIdioma]       = useState('')
  const [textoResumen, setTextoResumen] = useState('')
  const [opResumen,    setOpResumen]    = useState<number | null>(null)
  const [opImagen,     setOpImagen]     = useState<string | null>(opImagenInicial ?? null)
  // Guarda la categoria anterior para detectar cambios reales (evita reset en montaje inicial)
  const prevCategoria = useRef<TestCategory>(categoria)
  const [textoImagen,  setTextoImagen]  = useState('')

  // Estado de carga de fichero (solo categoria resumen)
  const [archivoNombre,   setArchivoNombre]   = useState<string | null>(null)
  const [cargandoArchivo, setCargandoArchivo] = useState(false)
  const [errorArchivo,    setErrorArchivo]    = useState<string | null>(null)
  const [palabrasArchivo, setPalabrasArchivo] = useState<number | null>(null)
  const [textoTruncado,   setTextoTruncado]   = useState(false)
  const [archivoReadonly, setArchivoReadonly] = useState(false)
  const archivoRef = useRef<HTMLInputElement>(null)
  const [generandoTexto,    setGenerandoTexto]    = useState(false)
  const [errorTextoEjemplo, setErrorTextoEjemplo] = useState<string | null>(null)
  const [llmEjemplo,        setLlmEjemplo]        = useState<string>('auto')
  const [textoAutogenerado, setTextoAutogenerado] = useState(false)
  const [showLoaderTexto,   setShowLoaderTexto]   = useState(false)

  // Estado de imagen subida para "describir imagen"
  const [imagenDescribirNombre,  setImagenDescribirNombre]  = useState<string | null>(null)
  const [imagenDescribirPreview, setImagenDescribirPreview] = useState<string | null>(null)
  const [errorImagenDescribir,   setErrorImagenDescribir]   = useState<string | null>(null)
  const imagenDescribirRef = useRef<HTMLInputElement>(null)

  // Modal de aviso de tamano de fichero
  const [modalTamano, setModalTamano] = useState<{ tipo: 'documento' | 'imagen'; limite: string } | null>(null)

  /* Sincronizar callbacks al restaurar la subcategoria de imagen tras volver del resultado */
  useEffect(() => {
    if (!opImagenInicial) return
    onInactivar?.(opImagenInicial === 'describir' ? [] : PROVEEDORES_SIN_IMAGEN)
    onSubcatImagenChange?.(opImagenInicial)
  }, []) // solo al montar; opImagenInicial y callbacks son estables

  /*
   * Calcula y emite la subcategoria_csv (solo para el CSV de admin).
   *   - lista (razonamiento/codigo/creativa/concretas) -> "N. Etiqueta"
   *   - traduccion -> idioma sin emoji ("Ingles", "Frances"...)
   *   - resumen    -> etiqueta de la opcion ("Resumen en 20 palabras"...)
   *   - imagen     -> id de la opcion ("generar"/"describir"/"logotipo"/"modificar")
   *   - libre      -> "Texto Libre"
   *   - resto sin opcion seleccionada -> null
   * Reacciona a cualquier cambio del estado relevante; mantiene sincronizado
   * el padre sin que SubcatPanel tenga que invocar al callback en cada handler.
   */
  useEffect(() => {
    if (!onSubcategoriaCsvChange) return
    let valor: string | null = null
    if (categoria in OPCIONES_LISTA) {
      if (subcatIdx !== null) {
        const etiqueta = OPCIONES_LISTA[categoria][subcatIdx]?.label ?? ''
        valor = `${subcatIdx + 1}. ${etiqueta}`
      }
    } else if (categoria === 'traduccion') {
      valor = idioma.replace(/^.{1,4} /, '')
    } else if (categoria === 'resumen') {
      if (opResumen !== null) valor = OPCIONES_RESUMEN[opResumen].label
    } else if (categoria === 'imagen') {
      valor = opImagen
    } else if (categoria === 'libre') {
      valor = 'Texto Libre'
    }
    onSubcategoriaCsvChange(valor)
  }, [categoria, subcatIdx, idioma, opResumen, opImagen, onSubcategoriaCsvChange])

  /* Resetear estado al cambiar de categoria */
  useEffect(() => {
    // Solo resetear cuando categoria cambia de verdad; en el montaje inicial prev === actual
    const cambio = prevCategoria.current !== categoria
    prevCategoria.current = categoria
    if (!cambio) return
    setSubcatIdx(null)
    setTextoTrad('')
    setIdioma('')
    setTextoResumen('')
    setOpResumen(null)
    setOpImagen(null)
    setTextoImagen('')
    setArchivoNombre(null)
    setCargandoArchivo(false)
    setErrorArchivo(null)
    setPalabrasArchivo(null)
    setTextoTruncado(false)
    setArchivoReadonly(false)
    setTextoAutogenerado(false)
    onTextoEntradaChange?.(null, false)
    if (archivoRef.current) archivoRef.current.value = ''
    setImagenDescribirNombre(null)
    setImagenDescribirPreview(null)
    setErrorImagenDescribir(null)
    if (imagenDescribirRef.current) imagenDescribirRef.current.value = ''
    onPromptChange('', false)
    onInactivar?.([])
    onSinSoporte?.([])
    onImagenChange?.(null, null)
    onSubcatImagenChange?.(null)
  }, [categoria]) // onPromptChange, onInactivar y onSinSoporte son estables (inline en el padre)

  const manejarArchivo = async (e: ChangeEvent<HTMLInputElement>) => {
    const archivo = e.target.files?.[0]
    if (!archivo) return

    // Limpia el input para que el mismo fichero pueda volver a seleccionarse
    if (archivoRef.current) archivoRef.current.value = ''

    // Validacion de tamano en cliente (igual que el limite del backend: 10 MB)
    if (archivo.size > 10 * 1024 * 1024) {
      setModalTamano({ tipo: 'documento', limite: '10 MB' })
      setArchivoNombre(null)
      return
    }

    // Resetea todo el estado del fichero anterior antes de la llamada async
    setTextoResumen('')
    setArchivoReadonly(false)
    setArchivoNombre(archivo.name)
    setPalabrasArchivo(null)
    setTextoTruncado(false)
    setErrorArchivo(null)
    setCargandoArchivo(true)

    try {
      const resultado = await extraerTextoFichero(archivo)
      setTextoResumen(resultado.texto)
      setArchivoReadonly(true)
      setPalabrasArchivo(resultado.palabras)
      setTextoTruncado(resultado.truncado)
      if (opResumen !== null) {
        onPromptChange(OPCIONES_RESUMEN[opResumen].prompt + resultado.texto, true)
      }
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      const mensaje = e?.response?.data?.detail ?? 'No se pudo extraer el texto del fichero.'
      setErrorArchivo(mensaje)
      setArchivoNombre(null)
      setTextoResumen('')
    } finally {
      setCargandoArchivo(false)
    }
  }

  /* ── Helpers para cada tipo ── */

  const elegirSubcat = (idx: number) => {
    setSubcatIdx(idx)
    const opcion = OPCIONES_LISTA[categoria]?.[idx]
    const prompt = opcion?.prompt ?? ''
    // En las categorias bilingues (razonamiento/creativa/concretas), todos los
    // prompts predefinidos llevan su traduccion. La validacion es defensiva:
    // si en el futuro se anade una opcion sin par EN, no rompemos el flujo
    // sino que caemos al comportamiento ES-only enviando prompt_en=null.
    const promptEn =
      esCategoriaBilingue(categoria) && opcion?.prompt_en ? opcion.prompt_en : null
    onPromptChange(prompt, true, promptEn)
  }

  const actualizarTraduccion = (texto: string, lang: string) => {
    const idiomaLimpio = lang.replace(/^.{1,4} /, '')
    const palabras = texto.trim().split(/\s+/).filter(Boolean).length
    if (lang && palabras >= 10) {
      onPromptChange(
        `Traduce el siguiente texto al ${idiomaLimpio}. Devuelve únicamente la traducción, sin explicaciones adicionales:\n\n"${texto}"`,
        true,
      )
    } else {
      onPromptChange('', false)
    }
  }

  const elegirOpResumen = (idx: number) => {
    setOpResumen(idx)
    const base = OPCIONES_RESUMEN[idx].prompt
    const palabras = textoResumen.trim().split(/\s+/).filter(Boolean).length
    if (palabras >= 300) {
      onPromptChange(base + textoResumen, true)
    } else {
      onPromptChange('', false)
    }
  }

  const actualizarResumen = (texto: string, autogenerado = false) => {
    setTextoResumen(texto)
    setTextoAutogenerado(autogenerado)
    onTextoEntradaChange?.(texto || null, autogenerado)
    const palabras = texto.trim().split(/\s+/).filter(Boolean).length
    if (opResumen !== null && palabras >= 300) {
      onPromptChange(OPCIONES_RESUMEN[opResumen].prompt + texto, true)
    } else {
      onPromptChange('', false)
    }
  }

  const handleGenerarTexto = async () => {
    setShowLoaderTexto(true)
    setGenerandoTexto(true)
    setErrorTextoEjemplo(null)
    // Al generar texto nuevo: limpiar archivo previo y marcar como editable
    setArchivoNombre(null)
    setPalabrasArchivo(null)
    setTextoTruncado(false)
    setArchivoReadonly(false)
    if (archivoRef.current) archivoRef.current.value = ''
    try {
      const proveedorParam = llmEjemplo === 'auto' ? undefined : llmEjemplo
      const respuesta = await generarTextoEjemplo(proveedorParam)
      actualizarResumen(respuesta.texto, true)
      // Dejar que BatLoader complete la animacion antes de ocultar el overlay
      setGenerandoTexto(false)
    } catch {
      setErrorTextoEjemplo('No se pudo generar el texto. Inténtalo de nuevo.')
      // En error: ocultar overlay de inmediato sin animacion
      setGenerandoTexto(false)
      setShowLoaderTexto(false)
    }
  }

  const elegirOpImagen = (id: string) => {
    setOpImagen(id)
    setTextoImagen('')
    // Al cambiar de opcion, limpiar la imagen subida
    setImagenDescribirNombre(null)
    setImagenDescribirPreview(null)
    setErrorImagenDescribir(null)
    if (imagenDescribirRef.current) imagenDescribirRef.current.value = ''
    onImagenChange?.(null, null)
    onSubcatImagenChange?.(id)
    const op = OPCIONES_IMAGEN.find((o) => o.id === id)
    if (op?.prompt) {
      onPromptChange(op.prompt, true)
    } else {
      onPromptChange('', false)
    }
    // Solo los proveedores con puedeGenerarImagenes=true participan en generar/editar
    onInactivar?.(id === 'describir' ? [] : PROVEEDORES_SIN_IMAGEN)
  }

  const manejarImagenDescribir = (e: ChangeEvent<HTMLInputElement>) => {
    const archivo = e.target.files?.[0]
    if (!archivo) return
    if (imagenDescribirRef.current) imagenDescribirRef.current.value = ''

    const MIME_PERMITIDOS = ['image/jpeg', 'image/jpg', 'image/png']
    if (!MIME_PERMITIDOS.includes(archivo.type)) {
      setErrorImagenDescribir('Formato no admitido. Usa JPG o PNG.')
      return
    }
    const LIMITE_BYTES = 5 * 1024 * 1024
    if (archivo.size > LIMITE_BYTES) {
      setModalTamano({ tipo: 'imagen', limite: '5 MB' })
      return
    }

    const reader = new FileReader()
    reader.onload = (ev) => {
      const dataUrl = ev.target?.result as string
      const separador = dataUrl.indexOf(',')
      const prefijo   = dataUrl.slice(0, separador)
      const b64       = dataUrl.slice(separador + 1)
      const mimeType  = prefijo.match(/data:([^;]+)/)?.[1] ?? 'image/jpeg'

      setImagenDescribirNombre(archivo.name)
      setImagenDescribirPreview(dataUrl)
      setErrorImagenDescribir(null)
      // Limpiar URL si habia una escrita
      setTextoImagen('')

      const instruccion = 'Describe con detalle esta imagen: identifica los elementos principales, los colores predominantes y el contexto que representa.'
      onPromptChange(instruccion, true)
      onImagenChange?.(b64, mimeType)
    }
    reader.readAsDataURL(archivo)
  }

  const manejarImagenModificar = (e: ChangeEvent<HTMLInputElement>) => {
    const archivo = e.target.files?.[0]
    if (!archivo) return
    if (imagenDescribirRef.current) imagenDescribirRef.current.value = ''

    const MIME_PERMITIDOS = ['image/jpeg', 'image/jpg', 'image/png']
    if (!MIME_PERMITIDOS.includes(archivo.type)) {
      setErrorImagenDescribir('Formato no admitido. Usa JPG o PNG.')
      return
    }
    const LIMITE_BYTES = 5 * 1024 * 1024
    if (archivo.size > LIMITE_BYTES) {
      setModalTamano({ tipo: 'imagen', limite: '5 MB' })
      return
    }

    const reader = new FileReader()
    reader.onload = (ev) => {
      const dataUrl = ev.target?.result as string
      const separador = dataUrl.indexOf(',')
      const prefijo   = dataUrl.slice(0, separador)
      const b64       = dataUrl.slice(separador + 1)
      const mimeType  = prefijo.match(/data:([^;]+)/)?.[1] ?? 'image/jpeg'

      setImagenDescribirNombre(archivo.name)
      setImagenDescribirPreview(dataUrl)
      setErrorImagenDescribir(null)
      setTextoImagen('')
      // El prompt se construye cuando el usuario escribe la instruccion en actualizarTextoImagen
      onImagenChange?.(b64, mimeType)
    }
    reader.readAsDataURL(archivo)
  }

  const actualizarTextoImagen = (texto: string) => {
    setTextoImagen(texto)
    const op = OPCIONES_IMAGEN.find((o) => o.id === opImagen)
    if (opImagen === 'generar') {
      onPromptChange(texto, false)
    } else if (opImagen === 'modificar') {
      onPromptChange(
        texto
          ? `Modifica la imagen adjunta aplicando el siguiente cambio: ${texto}`
          : '',
        !!texto,
      )
    } else if (op?.prompt) {
      onPromptChange(op.prompt + texto, true)
    }
  }

  const btnBase = 'w-full text-left rounded-lg px-3.5 py-2.5 border text-sm transition-all duration-150 cursor-pointer'

  /* ── Render segun tipo ── */
  return (
    <>
    <p className="text-base sm:text-xl font-semibold text-text uppercase tracking-widest mb-3 text-center
                   border border-text-alt/60 bg-primary/15 rounded-xl px-3 sm:px-5 py-2 sm:py-3">
      {SUBTITULOS_CAT[categoria]}
    </p>
    <div className="rounded-card border overflow-hidden shadow-card" style={{ borderColor: 'rgba(157,78,221,0.35)' }}>

      {/* Cabecera del panel */}
      <div className="flex items-center justify-between gap-4 px-4 py-3 border-b border-border"
           style={{ background: colorL }}>
        <div className="flex items-center gap-3 flex-shrink-0">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center text-lg flex-shrink-0"
               style={{ background: color }}>
            {categoria === 'razonamiento' && '🧩'}
            {categoria === 'codigo'       && '💻'}
            {categoria === 'creativa'     && '✍️'}
            {categoria === 'concretas'    && '🔍'}
            {categoria === 'traduccion'   && '🌐'}
            {categoria === 'resumen'      && '📄'}
            {categoria === 'imagen'       && '🖼️'}
            {categoria === 'libre'        && '💬'}
          </div>
          <p className="text-sm font-semibold min-w-0" style={{ color }}>
            {NOMBRES_CAT[categoria]}
          </p>
        </div>
        {/* Badge del sub-experimento bilingue ES vs EN.
            Solo aparece en razonamiento, creativa y concretas, las tres
            categorias donde cada prompt predefinido tiene un par EN validado
            (ADR-029). Visualmente avisa al usuario de que esta evaluacion
            sera doble: los 4 modelos responden en castellano (lo que se
            valora) y ademas en ingles (solo metricas tecnicas). */}
        {esCategoriaBilingue(categoria) && (
          <span
            className="text-[11px] sm:text-xs font-semibold uppercase tracking-wider
                       rounded-md px-2.5 py-1 border-2 whitespace-nowrap"
            style={{
              color,
              borderColor: color,
              background: color + '15',
              boxShadow: `0 0 8px ${color}40`,
            }}
            title="Las respuestas en inglés se generan solo para métricas comparativas; el humano valora únicamente las respuestas en castellano."
          >
            🌐 Comparación ES / EN
          </span>
        )}
      </div>

      {/* ── TIPO: lista ── */}
      {(categoria in OPCIONES_LISTA) && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 p-4">
          {OPCIONES_LISTA[categoria].map((op, i) => {
            const seleccionado = subcatIdx === i
            const hovering     = hoveredIdx === i && !seleccionado
            return (
              <button
                key={i}
                type="button"
                onClick={() => elegirSubcat(i)}
                onMouseEnter={() => setHoveredIdx(i)}
                onMouseLeave={() => setHoveredIdx(null)}
                className={`${btnBase} ${subcatIdx === null ? 'animate-pulse-strong' : ''}`}
                style={{
                  backgroundColor: seleccionado ? color
                                 : hovering      ? 'rgba(157,78,221,0.32)'
                                 :                 'rgba(157,78,221,0.07)',
                  borderColor:     seleccionado ? color
                                 : hovering      ? 'rgba(157,78,221,1)'
                                 :                 'rgba(157,78,221,0.5)',
                  color:           seleccionado ? '#fff'
                                 : hovering      ? '#FFFFFF'
                                 :                 TOKENS.muted,
                  transform:       hovering ? 'translateY(-2px)' : undefined,
                  boxShadow:       hovering ? `0 5px 18px rgba(157,78,221,0.55)` : undefined,
                }}
              >
                <span className="inline-flex items-center justify-center w-5 h-5
                                 rounded text-[11px] font-bold mr-2 align-middle"
                      style={{
                        background: seleccionado ? 'rgba(255,255,255,.25)'
                                  : hovering      ? 'rgba(157,78,221,0.35)'
                                  :                 'rgba(157,78,221,0.18)',
                        color:      seleccionado ? '#fff' : TOKENS.muted,
                      }}>
                  {i + 1}
                </span>
                {op.label}
              </button>
            )
          })}
        </div>
      )}

      {/* ── TIPO: traduccion ── */}
      {categoria === 'traduccion' && (
        <div className="p-4 space-y-3">
          <div>
            <label className="text-xs font-semibold text-muted block mb-1.5">
              Texto a traducir
            </label>
            <textarea
              className={`input-base resize-none h-24 text-sm ${
                textoTrad.trim().split(/\s+/).filter(Boolean).length < 10
                  ? 'animate-pulse-strong placeholder-glow'
                  : ''
              }`}
              placeholder="Escribe aquí el texto a traducir, mínimo 10 palabras..."
              value={textoTrad}
              onChange={(e) => {
                setTextoTrad(e.target.value)
                actualizarTraduccion(e.target.value, idioma)
              }}
            />
            {textoTrad.trim().length > 0 &&
              textoTrad.trim().split(/\s+/).filter(Boolean).length < 10 && (
                <p className="text-xs text-amber-400 mt-1">
                  {textoTrad.trim().split(/\s+/).filter(Boolean).length} / 10 palabras mínimas
                </p>
              )}
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs font-semibold text-muted whitespace-nowrap">Traducir a:</span>
            <select
              className={`input-base ${idioma === '' ? 'animate-pulse-strong' : ''}`}
              value={idioma}
              onChange={(e) => {
                setIdioma(e.target.value)
                actualizarTraduccion(textoTrad, e.target.value)
              }}
            >
              <option value="">— Selecciona idioma —</option>
              {IDIOMAS.map((l) => (
                <option key={l} value={l}>{l}</option>
              ))}
            </select>
          </div>
        </div>
      )}

      {/* ── TIPO: resumen ── */}
      {categoria === 'resumen' && (
        <div className="p-4 space-y-3">
          <div>
            <div className="flex flex-wrap items-center justify-between gap-2 mb-1.5">
              <label className="text-xs font-semibold text-muted">
                Texto a analizar (pega aquí el contenido)
              </label>
              <div className="flex items-center gap-2 flex-shrink-0">
                {/* Selector de LLM para generación de texto */}
                <select
                  className="input-base text-xs py-1.5 px-2"
                  value={llmEjemplo}
                  onChange={(e) => setLlmEjemplo(e.target.value)}
                  disabled={cargandoArchivo || generandoTexto}
                  title="Elige el LLM que generará el texto de ejemplo"
                >
                  <option value="auto">🤖 Auto</option>
                  <option value="gemini">🔵 Gemini</option>
                  <option value="grok">⚫ Grok</option>
                  <option value="openai">🟢 GPT-4o</option>
                  <option value="claude">🟠 Claude</option>
                </select>
                {/* Botón: generar texto con LLM */}
                <button
                  type="button"
                  className={`flex items-center gap-1.5 text-xs font-semibold
                             px-3 py-1.5 rounded-lg border-2 transition-all duration-150
                             hover:shadow-[0_0_22px_6px_rgba(245,245,240,0.75)] active:scale-95 disabled:opacity-40
                             ${!textoResumen && !cargandoArchivo && !generandoTexto ? 'animate-pulse-strong-white' : ''}`}
                  style={{
                    borderColor: TOKENS.textAlt,
                    color:       color,
                    background:  color + '18',
                  }}
                  onClick={handleGenerarTexto}
                  disabled={cargandoArchivo || generandoTexto || textoAutogenerado}
                >
                  <span>{generandoTexto ? '⏳' : '✨'}</span>
                  {generandoTexto ? 'Generando…' : 'Generar texto'}
                </button>
                {/* Botón: subir fichero */}
                <button
                  type="button"
                  className={`flex items-center gap-1.5 text-xs font-semibold
                             px-3 py-1.5 rounded-lg border-2 transition-all duration-150
                             hover:shadow-[0_0_22px_6px_rgba(245,245,240,0.75)] active:scale-95 disabled:opacity-40
                             ${!archivoNombre && !cargandoArchivo && !generandoTexto ? 'animate-pulse-strong-white' : ''}`}
                  style={{
                    borderColor: TOKENS.textAlt,
                    color:       color,
                    background:  color + '18',
                  }}
                  onClick={() => archivoRef.current?.click()}
                  disabled={cargandoArchivo || generandoTexto}
                >
                  <span>{cargandoArchivo ? '⏳' : '📎'}</span>
                  {cargandoArchivo ? 'Extrayendo…' : 'Subir fichero'}
                </button>
              </div>
              <input
                ref={archivoRef}
                type="file"
                accept=".txt,.pdf,.docx"
                className="hidden"
                onChange={manejarArchivo}
              />
            </div>
            <textarea
              className={`input-base resize-none h-24 overflow-y-auto text-sm ${
                !cargandoArchivo &&
                textoResumen.trim().split(/\s+/).filter(Boolean).length < 300
                  ? 'animate-pulse-strong placeholder-glow'
                  : ''
              }`}
              placeholder={cargandoArchivo
                ? 'Extrayendo texto del fichero…'
                : 'Pega aquí el texto a resumir o analizar, mínimo 300 palabras…'}
              value={textoResumen}
              readOnly={archivoReadonly || textoAutogenerado}
              style={{
                opacity:    archivoReadonly || textoAutogenerado ? 0.85 : 1,
                cursor:     archivoReadonly || textoAutogenerado ? 'default' : 'text',
                background: archivoReadonly || textoAutogenerado ? TOKENS.bg : undefined,
              }}
              onChange={(e) => !archivoReadonly && !textoAutogenerado && actualizarResumen(e.target.value)}
            />
            {textoAutogenerado && (
              <div className="flex items-center gap-3 mt-1 flex-wrap">
                <p className="text-[11px]" style={{ color: TOKENS.cat1 }}>
                  🔒 Texto autogenerado — solo lectura. Pulsa «Generar texto» para reemplazarlo o «Limpiar Texto» para recargar la opción.
                </p>
                <button
                  type="button"
                  className="flex items-center text-sm font-semibold px-3.5 py-1.5 rounded-lg border-2
                             transition-all duration-150 active:scale-95 flex-shrink-0
                             hover:shadow-[0_0_22px_6px_rgba(245,245,240,0.75)]"
                  style={{
                    borderColor: TOKENS.textAlt,
                    color:       TOKENS.textAlt,
                    background:  'transparent',
                  }}
                  onClick={() => { actualizarResumen('', false); setOpResumen(null) }}
                >
                  Limpiar Texto
                </button>
              </div>
            )}
            {!cargandoArchivo &&
              !textoAutogenerado &&
              textoResumen.trim().length > 0 &&
              textoResumen.trim().split(/\s+/).filter(Boolean).length < 300 && (
                <p className="text-xs text-amber-400 mt-1">
                  {textoResumen.trim().split(/\s+/).filter(Boolean).length} / 300 palabras mínimas
                </p>
              )}
            {errorTextoEjemplo && (
              <p className="text-xs text-red-400 mt-1">✕ {errorTextoEjemplo}</p>
            )}
            {archivoNombre && (
              <p className="text-[11px] text-muted mt-1 flex items-center gap-2 min-w-0">
                <span className="truncate">📎 {archivoNombre}</span>
                {palabrasArchivo !== null && (
                  <span
                    className="flex-shrink-0 font-semibold px-1.5 py-0.5 rounded-md"
                    style={{ color: color, background: color + '20' }}
                  >
                    {palabrasArchivo.toLocaleString('es-ES')} palabras
                  </span>
                )}
              </p>
            )}
            {palabrasArchivo !== null && palabrasArchivo > 5000 && !textoTruncado && (() => {
              const costeEstimado = (palabrasArchivo * 0.00001166 + 0.012).toFixed(2)
              return (
                <p className="text-[11px] text-yellow-400 mt-1">
                  💰 Texto largo — ejecución aprox. <strong>${costeEstimado}</strong> entre los 4 modelos.
                </p>
              )
            })()}
            {textoTruncado && (
              <p className="text-[11px] text-yellow-400 mt-1">
                ⚠️ El fichero supera las 8 000 palabras. Se ha cargado solo el inicio del texto.
              </p>
            )}
            {errorArchivo && (
              <p className="text-[11px] text-red-400 mt-1">✕ {errorArchivo}</p>
            )}
          </div>
          <div>
            <label className="text-xs font-semibold text-muted block mb-2">
              ¿Qué quieres hacer con el texto?
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
              {OPCIONES_RESUMEN.map((op, i) => {
                const sel = opResumen === i
                const hov = hoveredResumen === i && !sel
                return (
                  <button
                    key={i}
                    type="button"
                    onClick={() => elegirOpResumen(i)}
                    onMouseEnter={() => setHoveredResumen(i)}
                    onMouseLeave={() => setHoveredResumen(null)}
                    className={`flex flex-col items-center gap-1 p-2.5 rounded-lg border text-xs
                               text-center transition-all duration-150 cursor-pointer
                               ${opResumen === null ? 'animate-pulse-strong-white' : ''}`}
                    style={{
                      backgroundColor: sel ? color  : hov ? 'rgba(157,78,221,0.32)' : 'rgba(157,78,221,0.07)',
                      borderColor:     sel ? TOKENS.textAlt : hov ? TOKENS.textAlt : `${TOKENS.textAlt}59`,
                      color:           sel ? '#fff' : hov ? '#FFFFFF'    : TOKENS.muted,
                      transform:       hov ? 'translateY(-2px)' : undefined,
                      boxShadow:       sel || hov ? '0 0 22px 6px rgba(245,245,240,0.75)' : undefined,
                    }}
                  >
                    <span className="text-xl leading-none">{op.icon}</span>
                    <span className="leading-tight">{op.label}</span>
                  </button>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {/* ── TIPO: imagen ── */}
      {categoria === 'imagen' && (
        <div className="p-4 space-y-3">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {OPCIONES_IMAGEN.map((op) => {
              const sel = opImagen === op.id
              const hov = hoveredImagen === op.id && !sel
              return (
                <button
                  key={op.id}
                  type="button"
                  onClick={() => elegirOpImagen(op.id)}
                  onMouseEnter={() => setHoveredImagen(op.id)}
                  onMouseLeave={() => setHoveredImagen(null)}
                  className={`flex flex-col items-center gap-1.5 p-3 rounded-xl border-2
                             text-center transition-all duration-150 cursor-pointer
                             ${opImagen === null ? 'animate-pulse-strong-white' : ''}`}
                  style={{
                    backgroundColor: sel ? color  : hov ? 'rgba(157,78,221,0.32)' : 'rgba(157,78,221,0.07)',
                    borderColor:     sel ? TOKENS.textAlt : hov ? TOKENS.textAlt : `${TOKENS.textAlt}59`,
                    color:           sel ? '#fff' : hov ? '#FFFFFF'    : TOKENS.muted,
                    transform:       hov ? 'translateY(-2px)' : undefined,
                    boxShadow:       sel || hov ? '0 0 22px 6px rgba(245,245,240,0.75)' : undefined,
                  }}
                >
                  <span className="text-2xl leading-none">{op.icon}</span>
                  <span className="text-xs font-bold leading-tight">{op.label}</span>
                  <span className="text-[10px] leading-tight"
                        style={{ color: sel ? 'rgba(255,255,255,.75)' : hov ? '#E0DCF4' : TOKENS.muted }}>
                    {op.desc}
                  </span>
                </button>
              )
            })}
          </div>

          {/* Subpanel segun opcion imagen */}
          {opImagen === 'generar' && (
            <div>
              <label className="text-xs font-semibold text-muted block mb-1.5">
                Describe la imagen a generar
              </label>
              <textarea
                className={`input-base resize-none h-20 text-sm ${textoImagen === '' ? 'placeholder-glow' : ''}`}
                placeholder="Ej: Un dragón gótico volando sobre una ciudad medieval bajo luna llena…"
                value={textoImagen}
                onChange={(e) => actualizarTextoImagen(e.target.value)}
                autoFocus
              />
            </div>
          )}
          {(opImagen === 'describir') && (
            <div>
              <label className="text-xs font-semibold text-muted block mb-1.5">
                Imagen a describir
              </label>
              <button
                type="button"
                className={`flex items-center gap-1.5 text-xs font-semibold
                           px-3 py-1.5 rounded-lg border-2 transition-all duration-150
                           hover:brightness-110 active:scale-95
                           ${!imagenDescribirNombre ? 'animate-pulse-strong' : ''}`}
                style={{
                  borderColor: '#FFFFFF',
                  color:       color,
                  background:  color + '18',
                  boxShadow:   `0 0 8px ${color}40`,
                }}
                onClick={() => imagenDescribirRef.current?.click()}
              >
                <span>📸</span>
                {imagenDescribirNombre ? 'Cambiar imagen' : 'Subir imagen'}
              </button>
              <input
                ref={imagenDescribirRef}
                type="file"
                accept=".jpg,.jpeg,.png"
                className="hidden"
                onChange={manejarImagenDescribir}
              />
              {!imagenDescribirNombre && !errorImagenDescribir && (
                <p className="text-[11px] text-muted mt-1.5">
                  Formatos admitidos: JPG, PNG · máx. 5 MB
                </p>
              )}
              {imagenDescribirNombre && (
                <div className="mt-2 flex items-start gap-3">
                  {imagenDescribirPreview && (
                    <img
                      src={imagenDescribirPreview}
                      alt="Vista previa"
                      className="w-14 h-14 rounded-lg object-cover flex-shrink-0 border border-border"
                    />
                  )}
                  <div className="min-w-0">
                    <p className="text-[11px] text-muted truncate">📎 {imagenDescribirNombre}</p>
                    <p className="text-[10px] mt-0.5" style={{ color }}>Lista para analizar</p>
                  </div>
                </div>
              )}
              {errorImagenDescribir && (
                <p className="text-[11px] text-red-400 mt-1">✕ {errorImagenDescribir}</p>
              )}
            </div>
          )}
          {opImagen === 'logotipo' && (
            <div>
              <label className="text-xs font-semibold text-muted block mb-1.5">
                Empresa o concepto para el logotipo
              </label>
              <textarea
                className={`input-base resize-none h-20 text-sm ${textoImagen === '' ? 'placeholder-glow' : ''}`}
                placeholder="Ej: NovaMind, startup de apps de meditación, estilo zen, tonos azules y blancos…"
                value={textoImagen}
                onChange={(e) => actualizarTextoImagen(e.target.value)}
                autoFocus
              />
              <p className="text-[11px] text-muted mt-1.5">
                Incluye el nombre, sector y preferencias de color o estilo para mejores resultados.
              </p>
            </div>
          )}
          {opImagen === 'modificar' && (
            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-muted block mb-1.5">
                  Imagen a modificar
                </label>
                <button
                  type="button"
                  className={`flex items-center gap-1.5 text-xs font-semibold
                             px-3 py-1.5 rounded-lg border-2 transition-all duration-150
                             hover:brightness-110 active:scale-95
                             ${!imagenDescribirNombre ? 'animate-pulse-strong' : ''}`}
                  style={{
                    borderColor: '#FFFFFF',
                    color:       color,
                    background:  color + '18',
                    boxShadow:   `0 0 8px ${color}40`,
                  }}
                  onClick={() => imagenDescribirRef.current?.click()}
                >
                  <span>📸</span>
                  {imagenDescribirNombre ? 'Cambiar imagen' : 'Subir imagen a modificar'}
                </button>
                <input
                  ref={imagenDescribirRef}
                  type="file"
                  accept=".jpg,.jpeg,.png"
                  className="hidden"
                  onChange={manejarImagenModificar}
                />
                {!imagenDescribirNombre && !errorImagenDescribir && (
                  <p className="text-[11px] text-muted mt-1.5">
                    Formatos admitidos: JPG, PNG · máx. 5 MB
                  </p>
                )}
                {imagenDescribirNombre && (
                  <div className="mt-2 flex items-start gap-3">
                    {imagenDescribirPreview && (
                      <img
                        src={imagenDescribirPreview}
                        alt="Vista previa"
                        className="w-14 h-14 rounded-lg object-cover flex-shrink-0 border border-border"
                      />
                    )}
                    <div className="min-w-0">
                      <p className="text-[11px] text-muted truncate">📎 {imagenDescribirNombre}</p>
                      <p className="text-[10px] mt-0.5" style={{ color }}>Lista para modificar</p>
                    </div>
                  </div>
                )}
                {errorImagenDescribir && (
                  <p className="text-[11px] text-red-400 mt-1">✕ {errorImagenDescribir}</p>
                )}
              </div>
              <div>
                <label className="text-xs font-semibold text-muted block mb-1.5">
                  Instrucción de modificación
                </label>
                <textarea
                  className={`input-base resize-none h-20 text-sm ${textoImagen === '' ? 'placeholder-glow' : ''}`}
                  placeholder="Ej: Cambia el fondo a un atardecer en la playa…"
                  value={textoImagen}
                  onChange={(e) => actualizarTextoImagen(e.target.value)}
                />
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── TIPO: libre ── */}
      {categoria === 'libre' && (
        <div className="px-5 py-4 text-sm text-muted">
          💬 Escribe directamente en el área de texto lo que quieras comparar entre los modelos.
          Los resultados se guardarán como categoría <strong className="text-text">Texto libre</strong>.
        </div>
      )}

      {modalTamano && (
        <FileSizeModal
          tipo={modalTamano.tipo}
          limite={modalTamano.limite}
          onCerrar={() => setModalTamano(null)}
        />
      )}
    </div>

    {/* ── Overlay loader para "Generar texto" ─────────────────────────── */}
    {showLoaderTexto && (
      <div
        className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-4"
        style={{ background: 'rgba(0,0,0,0.72)', backdropFilter: 'blur(4px)' }}
      >
        <p className="text-base sm:text-lg font-semibold text-center px-4" style={{ color: TOKENS.textAlt }}>
          Generando texto aleatorio con el agente{' '}
          <span style={{ color: LLM_COLORES[llmEjemplo] ?? TOKENS.cat6 }}>
            {LLM_NOMBRES_DISPLAY[llmEjemplo] ?? llmEjemplo}
          </span>
        </p>
        <BatLoader
          modelos={[{ nombre: LLM_NOMBRES_DISPLAY[llmEjemplo] ?? llmEjemplo, color: LLM_COLORES[llmEjemplo] ?? TOKENS.cat6 }]}
          isLoading={generandoTexto}
          onComplete={() => setShowLoaderTexto(false)}
        />
      </div>
    )}
    </>
  )
}

const NOMBRES_CAT: Record<string, string> = {
  razonamiento: 'Razonamiento lógico',
  codigo:       'Generación de código',
  creativa:     'Escritura creativa',
  concretas:    'Preguntas concretas',
  traduccion:   'Traducción',
  resumen:      'Resumen',
  imagen:       'Imagen',
  libre:        'Texto libre',
}

const SUBTITULOS_CAT: Record<string, string> = {
  razonamiento: 'SEGUNDO PASO: Elige un acertijo de lógica para comparar',
  codigo:       'SEGUNDO PASO: Elige un reto de programación para comparar',
  creativa:     'SEGUNDO PASO: Elige un desafío de escritura para comparar',
  concretas:    'SEGUNDO PASO: Elige una pregunta de respuesta exacta',
  traduccion:   'SEGUNDO PASO: Escribe un texto y selecciona a qué idioma traducir',
  resumen:      'SEGUNDO PASO: Pega el texto o carga un documento y selecciona una acción a realizar',
  imagen:       'SEGUNDO PASO: Elige el tipo de operación que quieres realizar con imágenes',
  libre:        'SEGUNDO PASO: Escribe tu propio prompt en el área de texto',
}
