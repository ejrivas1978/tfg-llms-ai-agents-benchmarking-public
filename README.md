# Plataforma de Benchmarking de LLMs y Agentes de IA

Trabajo de Fin de Grado — Ingenieria Informatica  
Escuela Tecnica Superior de Ingenierias Informatica y de Telecomunicacion  
Universidad de Granada

**Autor:** Emilio Javier Rivas  
**Periodo:** Enero — Junio 2026

---

## Descripcion

Plataforma web para la evaluacion comparativa de modelos de lenguaje grande (LLMs).
Permite ejecutar baterias de pruebas sobre distintos modelos, recoger metricas de
rendimiento de forma automatica y combinarlas con valoraciones humanas para obtener
una vision completa del comportamiento de cada sistema.

Los modelos evaluados son Claude Sonnet 4.6 (Anthropic), GPT-4o (OpenAI),
Gemini 2.5 Flash (Google) y Grok 3 (xAI).

---

## Funcionalidades principales

- Ejecucion de benchmarks en paralelo sobre multiples LLMs con un mismo prompt
- Recogida automatica de metricas: latencia, tokens consumidos y coste estimado
- Evaluacion humana con criterios de calidad: precision, claridad, profundidad,
  creatividad, seguimiento de instrucciones, formato, tono y utilidad practica
- Dashboard interactivo con graficas comparativas por modelo y por categoria
- Exportacion de resultados a CSV y PDF
- Autenticacion de usuarios con roles (administrador, investigador, visualizador)

---

## Stack tecnologico

| Capa | Tecnologia |
|---|---|
| Backend | FastAPI (Python 3.11+) |
| Frontend | React 18 + TypeScript + Vite |
| Base de datos | PostgreSQL 15 + SQLAlchemy + Alembic |
| Contenedores | Docker + Docker Compose |
| Despliegue | Google Cloud Run |
| CI/CD | GitHub Actions |

---

## Arquitectura

El sistema sigue el patron MVC con separacion en capas:

```
Frontend (React)
    |
    v
API REST (FastAPI)
    |-- Capa de servicios (logica de negocio)
    |-- Capa de repositorios (acceso a datos)
    |-- Motor de LLMs (llamadas paralelas con asyncio)
    |
    v
PostgreSQL
```

Los patrones de diseno aplicados son Repository, Service Layer, Factory y Strategy,
documentados en el directorio `docs/decisions/` como Architecture Decision Records.

---

## Estructura del repositorio

```
tfg-llms-ai-agents-benchmarking/
|-- backend/                FastAPI + motor de LLMs
|   |-- app/
|   |   |-- core/           Configuracion, base de datos, seguridad
|   |   |-- models/         Modelos SQLAlchemy
|   |   |-- schemas/        Schemas Pydantic (DTOs)
|   |   |-- repositories/   Acceso a datos
|   |   |-- services/       Logica de negocio
|   |   |-- routers/        Endpoints REST
|   |   `-- llm_engine/     Clientes LLM y runner paralelo
|   `-- tests/
|-- frontend/               React + TypeScript
|   `-- src/
|       |-- components/
|       |-- pages/
|       |-- hooks/
|       `-- services/
|-- docs/                   Memoria, diagramas UML y decisiones
|-- docker-compose.yml
`-- .env.example
```

---

## Planificacion

El desarrollo se organiza en cuatro sprints:

| Sprint | Periodo | Objetivo |
|---|---|---|
| Sprint 1 | 01/01 — 31/01/2026 | Infraestructura y base de datos |
| Sprint 2 | 01/02 — 28/02/2026 | Motor de LLMs y API core |
| Sprint 3 | 01/03 — 30/04/2026 | Frontend y sistema de evaluacion |
| Sprint 4 | 01/05 — 01/06/2026 | Despliegue, tests y memoria final |

---

## Instalacion en local

Requisitos previos: Python 3.11+, Node.js 20+, Docker Desktop.

```bash
# 1. Clonar el repositorio
git clone https://github.com/ejrivas1978/tfg-llms-ai-agents-benchmarking.git
cd tfg-llms-ai-agents-benchmarking

# 2. Configurar variables de entorno
copy .env.example .env
# Editar .env con las API keys de cada proveedor LLM

# 3. Levantar la base de datos
docker-compose up -d postgres

# 4. Instalar dependencias del backend y ejecutar migraciones
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head

# 5. Instalar dependencias del frontend
cd ..\frontend
npm install

# 6. Arrancar los servicios
cd ..
docker-compose up -d
```

Acceso:
- Frontend: http://localhost:3000
- API docs: http://localhost:8000/docs

---

## Variables de entorno

Ver `.env.example` para la lista completa. Las variables principales son:

```
DATABASE_URL        Cadena de conexion a PostgreSQL
ANTHROPIC_API_KEY   Clave API de Anthropic (Claude Sonnet 4.6)
OPENAI_API_KEY      Clave API de OpenAI (GPT-4o + DALL-E 3)
GOOGLE_API_KEY      Clave API de Google AI (Gemini 2.5 Flash + Imagen 4)
XAI_API_KEY         Clave API de xAI (Grok 3 + grok-imagine-image)
SECRET_KEY          Clave secreta para tokens JWT de autenticacion
```

---

## Licencia

MIT License — ver fichero `LICENSE` para el texto completo.
