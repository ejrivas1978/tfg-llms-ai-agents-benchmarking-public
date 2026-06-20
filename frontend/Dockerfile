# ===========================================================
# Dockerfile — Frontend React + Nginx
# Ruta: frontend/Dockerfile
#
# Descripcion:
#     Imagen multi-stage para el frontend React.
#
#     Stage 1 (builder): compila el proyecto React con Vite.
#     Resultado: carpeta dist/ con HTML, JS y CSS optimizados.
#
#     Stage 2 (final): Nginx sirve los estaticos y hace de
#     proxy inverso hacia el backend de Cloud Run para las
#     rutas /api/.
#
#     He elegido nginx:1.27-alpine (no la imagen completa) para
#     obtener una imagen final de ~30 MB en lugar de ~150 MB.
#     La imagen alpine de nginx incluye el soporte de envsubst
#     para procesar nginx.conf.template automaticamente.
#
#     Variable de entorno requerida en Cloud Run:
#         BACKEND_URL  ej: https://backend-abc123-uc.a.run.app
#
# Sprint: Sprint 4
# ===========================================================

# ── Stage 1: build React ──────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Copio primero package.json y package-lock.json para aprovechar
# el cache de capas: si no cambian las dependencias, 'npm ci'
# no se vuelve a ejecutar aunque el codigo fuente cambie.
COPY package.json package-lock.json ./
RUN npm ci --prefer-offline

# Copio el codigo fuente
COPY . .

# Build de produccion con Vite + TypeScript
# La variable VITE_API_URL no es necesaria porque el frontend
# usa rutas relativas (/api/v1/...) que nginx proxia al backend.
RUN npm run build


# ── Stage 2: Nginx ────────────────────────────────────────
FROM nginx:1.27-alpine AS final

# He eliminado la configuracion por defecto de nginx porque
# voy a sustituirla completamente con mi template.
RUN rm /etc/nginx/conf.d/default.conf

# La imagen oficial de nginx procesa los ficheros en
# /etc/nginx/templates/*.template con envsubst al arrancar,
# copiando el resultado a /etc/nginx/conf.d/.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Copio los ficheros estaticos compilados por Vite
COPY --from=builder /app/dist /usr/share/nginx/html

# Cloud Run expone el servicio en el puerto 8080
EXPOSE 8080

# La imagen oficial de nginx arranca con CMD ["nginx", "-g", "daemon off;"]
# que se ejecuta despues de procesar los templates. No necesito
# sobreescribir CMD.
