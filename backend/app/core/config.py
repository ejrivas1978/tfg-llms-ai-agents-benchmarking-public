"""
Modulo: config
Ruta:   backend/app/core/config.py

Descripcion:
    Configuracion de la aplicacion cargada desde variables de entorno mediante
    Pydantic Settings v2. Los campos sensibles usan SecretStr para evitar que
    aparezcan en logs accidentalmente. Los ajustes se leen una unica vez al
    arrancar y se cachean con lru_cache.

    Uso:
        from app.core.config import get_settings
        settings = get_settings()

    En tests, limpia la cache antes de inyectar valores de prueba:
        get_settings.cache_clear()

Dependencias:
    - pydantic-settings>=2.5
    - python-dotenv>=1.0

Sprint: Sprint 1
"""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracion(BaseSettings):
    """Configuracion central del backend de benchmarking de LLMs.

    Lee los valores del fichero .env ubicado en backend/.env y de variables
    de entorno reales (las variables de entorno tienen precedencia sobre el fichero).

    He elegido SecretStr para las claves de API y la secret_key de JWT porque
    Pydantic enmascara automaticamente el valor en repr() y en logs:
    si alguien imprime el objeto settings por error, no aparecen las claves en texto plano.
    Solo se puede acceder al valor real llamando a .get_secret_value().

    He usado @lru_cache en get_settings() en lugar de un singleton global para
    que sea facil limpiar la cache en tests (get_settings.cache_clear()) e inyectar
    configuracion de prueba sin tener que parchear el modulo completo.

    Atributos:
        app_name: Nombre legible mostrado en el titulo de Swagger UI.
        app_version: Version semantica mostrada en Swagger UI.
        api_prefix: Prefijo de URL para todos los endpoints (ej: /api/v1).
        environment: Destino de ejecucion; controla valores por defecto y validaciones.
        debug: Activa trazas detalladas de error en las respuestas de la API.
        allowed_origins: Lista blanca de CORS; array JSON en .env.
        database_url: URL completa de conexion asincrona SQLAlchemy para PostgreSQL.
        secret_key: Clave HMAC usada para firmar los tokens JWT.
        algorithm: Algoritmo de firma JWT (HS256 simetrico).
        access_token_expire_minutes: Duracion del JWT en minutos.
        anthropic_api_key: Clave de API de Anthropic (Claude Sonnet 4.6).
        openai_api_key: Clave de API de OpenAI (GPT-4o + DALL-E 3 + gpt-image-1).
        google_api_key: Clave de Google AI Studio (Gemini 2.5 Flash + Imagen 4).
        xai_api_key: Clave de xAI (Grok 4.3 + grok-imagine-image).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # case_sensitive=False: permite que DATABASE_URL y database_url en .env
        # sean equivalentes. Facilita la configuracion en diferentes entornos
        # donde la convencion de nombre de variables puede variar.
        case_sensitive=False,
        # extra='ignore': el fichero .env de docker-compose incluye variables como
        # POSTGRES_DB que no son campos de Configuracion. Sin este ajuste, pydantic
        # lanzaria un error de validacion al encontrar esas variables extra.
        extra="ignore",
    )

    # --- Metadatos de la aplicacion ---
    app_name: str = "TFG LLM Benchmarking API"
    app_version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False

    # --- CORS ---
    # He usado lista[str] en lugar de str para que pydantic-settings decodifique
    # automaticamente el JSON del .env: ALLOWED_ORIGINS=["http://localhost:5173"].
    # En desarrollo apunto solo al puerto de Vite; en produccion se sobreescribe
    # con la URL de Cloud Run.
    allowed_origins: list[str] = ["http://localhost:5173"]

    # --- Base de datos ---
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/tfg_llm_db"
    )

    # --- Autenticacion JWT ---
    # IMPORTANTE: sobreescribir SECRET_KEY en .env con un valor aleatorio de minimo 32 bytes.
    # Comando para generar uno: openssl rand -hex 32
    # El valor por defecto 'change_me_in_production' activa una advertencia en el arranque
    # si environment=='production', para evitar despliegues con la clave por defecto.
    secret_key: SecretStr = SecretStr("change_me_in_production")
    algorithm: str = "HS256"
    # He reducido la duracion del token de 8h (valor inicial) a 2h como medida
    # de seguridad: un token de admin con 8h de vida es una ventana de exposicion
    # muy larga si el token quedara comprometido. 2h es suficiente para una sesion
    # de trabajo normal y reduce el riesgo de uso no autorizado.
    access_token_expire_minutes: int = 120  # 2 horas; sobreescribible via .env

    # --- Proveedores LLM ---
    # He hecho todos los campos opcionales (SecretStr | None) para que la aplicacion
    # arranque aunque no esten todas las claves configuradas. Esto facilita el
    # desarrollo con un subconjunto de proveedores y permite que el runner omita
    # los clientes sin clave en lugar de lanzar un error al arrancar.
    anthropic_api_key: SecretStr | None = None   # Claude Sonnet 4.6
    openai_api_key: SecretStr | None = None       # GPT-4o + DALL-E 3 + gpt-image-1
    google_api_key: SecretStr | None = None       # Gemini 2.5 Flash + Imagen 4
    xai_api_key: SecretStr | None = None          # Grok 4.3 + grok-imagine-image

    # --- Variables de PostgreSQL para docker-compose (no usadas por FastAPI) ---
    # He declarado estos campos aqui para que pydantic no lance ValidationError
    # cuando el .env de docker-compose contiene POSTGRES_DB, POSTGRES_USER, etc.
    # Sin estas declaraciones y con extra='ignore' ya no serian problema, pero
    # las mantengo por claridad de que son variables conocidas y esperadas.
    postgres_db: str = "tfg_llm_db"
    postgres_user: str = "postgres"
    postgres_password: SecretStr = SecretStr("postgres")
    postgres_port: int = 5432

    # --- Variables de pgAdmin para docker-compose ---
    pgadmin_email: str = "admin@tfg.local"
    pgadmin_password: SecretStr = SecretStr("admin")
    pgadmin_port: int = 5050


# Alias en ingles para mantener compatibilidad con imports existentes en otros modulos.
# He conservado este alias porque varios modulos importan 'Settings' directamente.
Settings = Configuracion


@lru_cache
def get_settings() -> Configuracion:
    """Devuelve el singleton de configuracion de la aplicacion, cacheado con lru_cache.

    He elegido lru_cache sobre un modulo-nivel singleton porque lru_cache permite
    limpiar la cache en tests llamando a get_settings.cache_clear() sin necesidad
    de parchear el modulo. Si usara una variable global, los tests tendrian que
    usar monkeypatch o importar el modulo y modificar el atributo directamente,
    lo que es mas fragil y dificil de entender.

    Returns:
        Instancia de Configuracion poblada desde variables de entorno y .env.
    """
    return Configuracion()
