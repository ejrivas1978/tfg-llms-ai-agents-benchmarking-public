# ADR-021: Carga de ficheros para la categoría resumen

Estado: Aceptado
Fecha: 03/05/2026
Sprint: Sprint 4
DEF relacionada: ADR-014-subcategorias-capa-presentacion.md

## Contexto

La categoría de resumen permite al evaluador elegir una operación sobre un
texto (resume en 20 palabras, esquema jerárquico, 5 preguntas clave, etc.).
Hasta este punto, el evaluador debía pegar el texto a analizar manualmente
en el textarea del panel. Para documentos largos —informes técnicos, artículos
académicos, capítulos de libros— el proceso de copiar y pegar era impracticable,
especialmente con ficheros en formato PDF o DOCX.

Se evaluó incorporar la capacidad de cargar un fichero directamente desde la
interfaz y extraer su contenido de texto de forma automática.

## Opciones evaluadas

### Opción A — Extracción en el cliente (JavaScript)

Usar librerías JavaScript (`pdf.js`, `mammoth.js`) en el navegador para extraer
texto del fichero antes de enviarlo al backend.

**Pros:**
- No requiere nuevos endpoints en el backend.
- Extracción instantánea sin latencia de red.

**Contras:**
- `pdf.js` pesa ~1 MB adicional en el bundle del frontend.
- La calidad de extracción de PDF es notablemente inferior a la de las librerías
  Python (`pdfplumber`), especialmente en PDFs con columnas o tablas.
- Añade complejidad al frontend con lógica que no es de su responsabilidad.
- Los workers de `pdf.js` son difíciles de configurar en Vite.

### Opción B — Extracción en el backend (Python) ✓ Elegida

Crear un endpoint dedicado `POST /api/v1/upload/extraer-texto` que recibe el
fichero como `multipart/form-data`, extrae el texto con librerías Python
especializadas y devuelve el texto plano al frontend.

**Pros:**
- `pdfplumber` ofrece extracción de alta calidad para PDFs complejos.
- `python-docx` es el estándar para ficheros `.docx`.
- La lógica de extracción queda centralizada en el backend, donde pertenece.
- El frontend queda limpio: solo envía el fichero y recibe texto.
- Facilita la adición futura de nuevos formatos sin cambios en el frontend.

**Contras:**
- Requiere un nuevo endpoint y dos nuevas dependencias Python.
- Añade una llamada de red antes de la llamada principal al benchmark.

## Decisión

Se elige la **Opción B**. La extracción en el backend es más robusta, mantiene
la separación de responsabilidades y produce texto de mayor calidad para el
análisis posterior por los modelos de lenguaje.

## Implementación

### Backend

**`backend/app/routers/upload_router.py`** (nuevo):

```
POST /api/v1/upload/extraer-texto
  Body:    multipart/form-data — campo "archivo"
  Acepta:  .txt, .pdf, .docx
  Límites: 10 MB por fichero · 8 000 palabras en la respuesta
  Devuelve: { texto: str, palabras: int, truncado: bool }
```

- `.txt`: decodificación con fallback UTF-8 → latin-1 → cp1252.
- `.pdf`: extracción página a página con `pdfplumber`.
- `.docx`: extracción de párrafos con `python-docx`.
- Si el texto extraído supera 8 000 palabras, se trunca y se indica con
  `truncado: true`. El límite se justifica por criterios de coste (ver sección
  siguiente) y no por los límites de contexto de los modelos.

**`backend/requirements.txt`**:
- `pdfplumber==0.11.4`
- `python-docx==1.1.2`

**`backend/app/schemas/benchmark.py`**:
- `PeticionBenchmark.prompt`: `max_length` ampliado de 8 000 a 65 000 caracteres.
  El límite original estaba pensado para prompts escritos a mano. Un documento
  de 8 000 palabras genera un prompt ensamblado de ~60 000 caracteres
  (prefijo del template + texto del fichero).

### Frontend

**`frontend/src/services/uploadApi.ts`** (nuevo):
- `extraerTextoFichero(archivo: File): Promise<TextoExtraido>` — POST al endpoint
  con `FormData`.

**`frontend/src/components/benchmark/SubcatPanel.tsx`** (modificado, bloque resumen):
- Botón **📎 Subir fichero** junto a la etiqueta "Texto a analizar".
- Input `type="file"` oculto activado por ref para prescindir del estilo nativo.
- Al cargar el fichero: el texto reemplaza el contenido del textarea, que queda
  bloqueado para edición. El textarea anterior se borra antes de la llamada
  asíncrona para evitar acumulación de contenido al cargar un segundo fichero.
- Badge con nombre del fichero y contador de palabras en el color de la categoría.
- El input se resetea tras cada carga para permitir reseleccionar el mismo fichero.

## Decisión sobre el límite de palabras

El límite de 8 000 palabras no está determinado por las ventanas de contexto de
los modelos (el modelo más restrictivo, GPT-4o, admite ~83 000 palabras), sino
por el coste por ejecución. Al enviar el mismo texto a los cuatro modelos
simultáneamente, el coste escala linealmente con el volumen:

| Palabras | Tokens entrada aprox. | Coste estimado (4 modelos) |
|---|---|---|
| 5 000 | 6 750 | ≈ $0,07 |
| 8 000 | 10 800 | ≈ $0,11 |
| 20 000 | 27 000 | ≈ $0,25 |
| 80 000 | 108 000 | ≈ $0,95 |

*Tarifas mayo 2026: Claude $3/M entrada · GPT-4o $2,50/M · Gemini $0,15/M · Grok $3/M.*

8 000 palabras es suficiente para documentos técnicos reales (un capítulo de libro,
un informe de 20 páginas) y mantiene el coste por ejecución por debajo de $0,12.
A partir de 5 000 palabras la interfaz muestra un aviso con el coste estimado.

El análisis completo y la fórmula de estimación están documentados en
`docs/memoria/chapters/refinamiento_metricas_sesgo.md`.

## Consecuencias

Positivas:
- El evaluador puede analizar documentos reales sin copiar y pegar.
- La extracción es robusta para los tres formatos más habituales en entornos
  profesionales y académicos.
- El coste por ejecución está acotado y es visible para el usuario.

Trade-offs asumidos:
- El límite de 8 000 palabras excluye documentos muy largos (libros completos,
  informes extensos). Para el objetivo del TFG —comparar la calidad de resumen
  de los modelos— este límite es adecuado.
- La extracción de PDFs con imágenes, formularios o protección por contraseña
  devuelve error 422 con un mensaje descriptivo al usuario.
- La latencia adicional de la extracción (~0,5-2 s según el tamaño del fichero)
  es visible para el usuario durante el estado "⏳ Extrayendo…" del botón.
