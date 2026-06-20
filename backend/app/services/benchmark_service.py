"""
Modulo: services.benchmark_service
Ruta:   backend/app/services/benchmark_service.py

Descripcion:
    Capa de servicio para la ejecucion y persistencia de evaluaciones de benchmark.
    Orquesta el flujo completo: creacion de la evaluacion, llamadas paralelas a los LLMs,
    calculo de metricas derivadas, persistencia de resultados y similitud Jaccard.

    DECISION(ADR-003): Service Layer mantiene la logica de negocio desacoplada
    del ORM y de los endpoints HTTP.
    DECISION(ADR-004): Las llamadas a los LLMs se ejecutan en paralelo con
    asyncio.gather y return_exceptions=True.
    DECISION(ADR-011): La categoria imagen filtra solo los clientes con
    SOPORTA_IMAGEN=True. El resto ejecutan los cuatro proveedores.

Dependencias:
    - app.core.config
    - app.llm_engine.metricas
    - app.llm_engine.runner
    - app.models.enums
    - app.repositories.benchmark_evaluacion_repository
    - app.repositories.llm_response_repository
    - app.schemas.benchmark

Sprint: Sprint 2
"""

import logging
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.usuario_app import UsuarioApp
from app.repositories.usuario_app_repository import UsuarioAppRepository
from app.llm_engine.metricas import (
    calcular_coste_imagen_usd,
    calcular_coste_usd,
    calcular_metricas_texto,
    calcular_similitud_jaccard_media,
)
from app.llm_engine.resultado import ResultadoLLM
from app.llm_engine.runner import construir_clientes, ejecutar_benchmark
from app.models.enums import SessionStatus, TestCategory
from app.repositories.benchmark_evaluacion_repository import BenchmarkEvaluacionRepository
from app.repositories.llm_response_repository import LLMResponseRepository
from app.schemas.benchmark import RespuestaBenchmark, RespuestaLLMDTO, RespuestaTextoEjemplo

logger = logging.getLogger(__name__)


class BenchmarkService:
    """Capa de servicio para la ejecucion y persistencia de benchmarks.

    Orquesta el flujo completo: crea la evaluacion, invoca el runner paralelo,
    enriquece cada resultado con sus metricas derivadas, persiste las respuestas
    y calcula la similitud Jaccard media entre proveedores.
    Los errores parciales de un proveedor se persisten sin abortar la evaluacion.

    Atributos:
        _db: Sesion asincrona SQLAlchemy inyectada via dependencia FastAPI.
        _benchmark_repo: Repositorio de BenchmarkEvaluacion.
        _respuesta_repo: Repositorio de LLMResponse.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Inicializa el servicio con sus repositorios.

        Args:
            db: AsyncSession proporcionada por la dependencia get_db de FastAPI.
        """
        self._db = db
        self._benchmark_repo = BenchmarkEvaluacionRepository(db)
        self._respuesta_repo = LLMResponseRepository(db)
        self._usuario_repo = UsuarioAppRepository(db)

    # Categorias que activan la comparativa bilingue ES/EN cuando se elige
    # un prompt predefinido. Definido a nivel de clase para que el dashboard
    # tambien lo consulte y mantenga sincronizacion.
    CATEGORIAS_BILINGUES: tuple[TestCategory, ...] = (
        TestCategory.razonamiento,
        TestCategory.creativa,
        TestCategory.concretas,
        TestCategory.codigo,
    )

    # Limite de tokens de salida por categoria.
    # Las categorias con respuestas largas (razonamiento paso a paso, codigo
    # con implementacion completa, escritura creativa) necesitan mas tokens
    # para no truncar. Las APIs admiten hasta 8192 via endpoint compat-OpenAI.
    # Gemini 2.5 Flash es el mas propenso a truncar en razonamiento porque
    # genera explicaciones detalladas de cada paso.
    _MAX_TOKENS: dict[TestCategory, int] = {
        TestCategory.razonamiento: 8192,
        TestCategory.codigo:       8192,
        TestCategory.creativa:     8192,
        TestCategory.resumen:      8192,
        TestCategory.traduccion:   6144,
        TestCategory.libre:        8192,
        TestCategory.concretas:    4096,
        TestCategory.imagen:       4096,
    }

    async def ejecutar(
        self,
        nickname: str,
        prompt: str,
        categoria: TestCategory,
        imagen_base64: str | None = None,
        imagen_mime_type: str | None = None,
        subcat_imagen: str | None = None,
        subcategoria_csv: str | None = None,
        usuario_app: UsuarioApp | None = None,
        prompt_en: str | None = None,
        texto_entrada: str | None = None,
        texto_entrada_autogenerado: bool = False,
    ) -> RespuestaBenchmark:
        """Ejecuta un benchmark completo y persiste todos los resultados.

        Flujo:
          1. Verifica cuota del usuario si es usuario web (no admin).
          2. Construye los clientes LLM activos segun la configuracion.
          3. Crea la evaluacion en estado en_curso.
          4. Llama a todos los LLMs en paralelo con asyncio.gather.
          5. Enriquece cada resultado con sus metricas derivadas.
          6. Persiste cada resultado como LLMResponse en la base de datos.
          7. Calcula y guarda la similitud Jaccard media de la evaluacion.
          8. Marca la evaluacion como completada (hay exito) o fallida (todo error).
          9. Consume una consulta del usuario si la evaluacion fue completada.

        Args:
            nickname: Alias del evaluador para la evaluacion.
            prompt: Texto del prompt a enviar a todos los LLMs.
            categoria: Categoria del benchmark para el dashboard.
            imagen_base64: Base64 de la imagen subida para analisis vision (sin prefijo data-URI).
            imagen_mime_type: MIME type de la imagen de vision.
            subcat_imagen: Subcategoria de imagen ('describir', 'generar', 'modificar').
            usuario_app: Usuario web autenticado. None si es administrador (cuota ilimitada).

        Returns:
            RespuestaBenchmark con la evaluacion completa y todas las respuestas.

        Raises:
            HTTPException 402: Si el usuario web ha agotado su cuota de consultas.
            HTTPException 503: Si no hay ningun cliente LLM configurado.
        """
        # Verificar cuota antes de lanzar las llamadas LLM (solo usuarios web)
        if usuario_app is not None and usuario_app.consultas_usadas >= usuario_app.cuota_asignada:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Has agotado tu cuota de consultas. Solicita mas tokens al administrador.",
            )
        settings = get_settings()
        clientes = construir_clientes(
            anthropic_key=settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else None,
            openai_key=settings.openai_api_key.get_secret_value() if settings.openai_api_key else None,
            google_key=settings.google_api_key.get_secret_value() if settings.google_api_key else None,
            xai_key=settings.xai_api_key.get_secret_value() if settings.xai_api_key else None,
        )

        if not clientes:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No hay proveedores LLM configurados. Revisa las variables de entorno.",
            )

        # 'describir' siempre usa completar() (vision/texto) aunque no haya fichero subido.
        # 'modificar' sube imagen de referencia pero la ruta es edicion de imagen (es_imagen=True);
        # el runner detecta imagen_base64 + es_imagen=True y llama a editar_imagen().
        es_descripcion = subcat_imagen == "describir"
        es_imagen = categoria == TestCategory.imagen and not es_descripcion

        evaluacion = await self._benchmark_repo.crear(
            nickname=nickname,
            prompt=prompt,
            categoria=categoria,
            es_generacion_imagen=es_imagen,
            subcategoria_csv=subcategoria_csv,
            texto_entrada=texto_entrada,
            texto_entrada_autogenerado=texto_entrada_autogenerado,
        )
        await self._benchmark_repo.actualizar_estado(evaluacion, SessionStatus.en_curso)

        # Comparativa bilingue ES/EN: cuando la categoria participa Y el
        # frontend ha pasado un prompt EN traducido, se hacen DOS rondas
        # secuenciales (no concurrentes para no doblar la presion sobre cada
        # API). La cuota del usuario solo descuenta UNA consulta porque la
        # experiencia humana es una sola pregunta (las 4 respuestas EN no se
        # valoran, solo sirven para metricas automaticas comparativas).
        comparativa_es_en = (
            categoria in self.CATEGORIAS_BILINGUES
            and prompt_en is not None
            and prompt_en.strip() != ""
        )

        max_tokens = self._MAX_TOKENS.get(categoria, 4096)

        resultados = await ejecutar_benchmark(
            clientes, prompt,
            es_imagen=es_imagen,
            imagen_base64=imagen_base64,
            imagen_mime_type=imagen_mime_type,
            idioma_prompt='es',
            max_tokens=max_tokens,
        )

        if comparativa_es_en:
            resultados_en = await ejecutar_benchmark(
                clientes, prompt_en,  # type: ignore[arg-type]
                es_imagen=es_imagen,
                imagen_base64=imagen_base64,
                imagen_mime_type=imagen_mime_type,
                idioma_prompt='en',
                max_tokens=max_tokens,
            )
            resultados.extend(resultados_en)

        respuestas_orm = []
        for resultado in resultados:
            resultado_enriquecido = self._enriquecer_resultado(resultado)
            resp_orm = await self._respuesta_repo.crear_desde_resultado(
                evaluacion.id, resultado_enriquecido
            )
            respuestas_orm.append(resp_orm)

        # Jaccard se calcula SOLO entre las respuestas en castellano: la
        # comparativa bilingue produce respuestas EN que no son comparables
        # lexicamente con las ES (lenguaje diferente, vocabulario distinto).
        # Mezclarlas dejaria el Jaccard medio artificialmente bajo y sesgaria
        # la metrica del dashboard.
        textos = [
            r.texto_respuesta
            for r in resultados
            if not r.tuvo_error and not r.es_imagen and r.idioma_prompt == 'es'
        ]
        jaccard = calcular_similitud_jaccard_media(textos)
        await self._benchmark_repo.actualizar_jaccard(evaluacion, jaccard)

        hay_exito = any(not r.tuvo_error for r in resultados)
        hay_censura = any(self._es_rechazo_politica(r) for r in resultados)
        # Si cualquier modelo de imagen fallo (aunque otros LLMs de texto respondieran),
        # la evaluacion cae a fallida para evitar sesgo: valorar solo los que si generaron
        # imagen artificialmente los favorece frente al modelo que no pudo responder.
        hay_error_imagen = any(r.tuvo_error and r.es_imagen for r in resultados)
        if not hay_exito or hay_censura or hay_error_imagen:
            estado_final = SessionStatus.fallida
        else:
            estado_final = SessionStatus.completada
        evaluacion.completed_at = datetime.now(timezone.utc)
        await self._benchmark_repo.actualizar_estado(evaluacion, estado_final)

        # Consumir una consulta solo si la evaluacion se completo con exito
        # (sin error total ni rechazo por politica de contenido)
        if usuario_app is not None and estado_final == SessionStatus.completada:
            await self._usuario_repo.incrementar_consultas(usuario_app)

        logger.info(
            "Benchmark completado: evaluacion_id=%d, proveedores=%d, jaccard=%s",
            evaluacion.id,
            len(resultados),
            jaccard,
        )

        return self._construir_dto(evaluacion, respuestas_orm, es_imagen)

    _CENSURA_KW = (
        "content moderation", "content_policy", "politicas de seguridad",
        "filtros de seguridad", "safety system", "contenido bloqueado",
        "contenido rechazado",
    )

    def _es_rechazo_politica(self, resultado: ResultadoLLM) -> bool:
        """Devuelve True si el resultado tiene un error de politica de contenido."""
        if not resultado.tuvo_error or not resultado.mensaje_error:
            return False
        msg = resultado.mensaje_error.lower()
        return any(kw in msg for kw in self._CENSURA_KW)

    def _enriquecer_resultado(self, resultado: ResultadoLLM) -> ResultadoLLM:
        """Calcula y asigna las metricas derivadas sobre un resultado LLM.

        Para respuestas correctas de texto calcula todas las metricas de
        rendimiento y de analisis del texto. Para imagenes asigna el coste
        fijo por imagen. Los resultados con error no se procesan.

        Args:
            resultado: ResultadoLLM con datos brutos devueltos por la API.

        Returns:
            El mismo ResultadoLLM con los campos de metricas rellenados.
        """
        if resultado.tuvo_error:
            return resultado

        if resultado.es_imagen:
            resultado.coste_usd = calcular_coste_imagen_usd(resultado.proveedor)
            return resultado

        resultado.coste_usd = calcular_coste_usd(
            resultado.proveedor,
            resultado.tokens_entrada,
            resultado.tokens_salida,
            resultado.tokens_entrada_cacheados,
        )
        metricas = calcular_metricas_texto(
            texto=resultado.texto_respuesta or "",
            tokens_entrada=resultado.tokens_entrada,
            tokens_salida=resultado.tokens_salida,
            latencia_ms=resultado.latencia_ms,
            coste_usd=resultado.coste_usd,
        )
        resultado.tokens_por_segundo = metricas["tokens_por_segundo"]
        resultado.ratio_sal_ent = metricas["ratio_sal_ent"]
        resultado.coste_por_100_palabras = metricas["coste_por_100_palabras"]
        resultado.palabras = metricas["palabras"]
        resultado.diversidad_lexica = metricas["diversidad_lexica"]
        resultado.parrafos = metricas["parrafos"]
        return resultado

    def _construir_dto(
        self, evaluacion, respuestas_orm, es_imagen: bool
    ) -> RespuestaBenchmark:
        """Construye el DTO RespuestaBenchmark a partir de los objetos ORM.

        Mapea explicitamente los nombres de campo del modelo ORM a los del
        esquema Pydantic. Para evaluaciones de imagen, response_text se trata
        como la URL/data-URI de la imagen generada.

        Args:
            evaluacion: Instancia de BenchmarkEvaluacion persistida.
            respuestas_orm: Lista de instancias LLMResponse persistidas.
            es_imagen: True si la evaluacion es de generacion de imagen.

        Returns:
            RespuestaBenchmark listo para serializar en la respuesta HTTP.
        """
        dtos = [
            RespuestaLLMDTO(
                id=r.id,
                proveedor=r.provider,
                modelo=r.model_name,
                texto_respuesta=None if es_imagen else r.response_text,
                tokens_entrada=r.input_tokens,
                tokens_salida=r.output_tokens,
                latencia_ms=r.latency_ms,
                tokens_por_segundo=float(r.tokens_por_segundo),
                ratio_sal_ent=float(r.ratio_sal_ent),
                cost_usd=float(r.cost_usd),
                coste_por_100_palabras=float(r.coste_por_100_palabras),
                palabras=r.palabras,
                diversidad_lexica=float(r.diversidad_lexica),
                parrafos=r.parrafos,
                tuvo_error=r.tuvo_error,
                mensaje_error=r.error_message,
                es_imagen=es_imagen,
                url_imagen=r.response_text if es_imagen else None,
                imagen_miniatura=r.imagen_miniatura if es_imagen else None,
                idioma_prompt=r.idioma_prompt,
            )
            for r in respuestas_orm
        ]
        return RespuestaBenchmark(
            id=evaluacion.id,
            nickname=evaluacion.nickname,
            prompt=evaluacion.prompt,
            categoria=evaluacion.category,
            estado=evaluacion.status,
            similitud_jaccard_media=evaluacion.similitud_jaccard_media,
            created_at=evaluacion.created_at,
            completed_at=evaluacion.completed_at,
            respuestas=dtos,
            texto_entrada=evaluacion.texto_entrada,
            texto_entrada_autogenerado=evaluacion.texto_entrada_autogenerado,
        )

    async def obtener_por_id(self, evaluacion_id: int) -> RespuestaBenchmark:
        """Recupera una evaluacion de benchmark con todas sus respuestas LLM.

        Args:
            evaluacion_id: ID de la evaluacion a recuperar.

        Returns:
            RespuestaBenchmark con la evaluacion y sus respuestas.

        Raises:
            HTTPException 404: Si la evaluacion no existe.
        """
        evaluacion = await self._benchmark_repo.obtener_por_id(evaluacion_id)
        if evaluacion is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Evaluacion {evaluacion_id} no encontrada",
            )
        return self._construir_dto(evaluacion, evaluacion.respuestas, evaluacion.es_generacion_imagen)

    # Mapeo de alias frontend -> valor LLMProvider para el selector de proveedor.
    _ALIAS_PROVEEDOR: dict[str, str] = {
        "claude":  "anthropic",
        "openai":  "openai",
        "gemini":  "google",
        "grok":    "xai",
    }

    async def generar_texto_ejemplo(
        self,
        proveedor_preferido: str | None = None,
    ) -> RespuestaTextoEjemplo:
        """Genera un texto en castellano de ~300 palabras con el LLM indicado.

        Si proveedor_preferido es None, usa el primer cliente disponible.
        Si se especifica un proveedor, lo busca en la lista de clientes activos;
        si no esta disponible devuelve 503 sin intentar otro (eleccion explicita).

        Args:
            proveedor_preferido: Alias del proveedor ('claude', 'openai', 'gemini', 'grok')
                                 o None para seleccion automatica.

        Returns:
            RespuestaTextoEjemplo con el texto, el numero de palabras y el proveedor.

        Raises:
            HTTPException 400: Alias de proveedor desconocido.
            HTTPException 503: Proveedor no configurado o llamada fallida.
        """
        settings = get_settings()
        clientes = construir_clientes(
            anthropic_key=settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else None,
            openai_key=settings.openai_api_key.get_secret_value() if settings.openai_api_key else None,
            google_key=settings.google_api_key.get_secret_value() if settings.google_api_key else None,
            xai_key=settings.xai_api_key.get_secret_value() if settings.xai_api_key else None,
        )
        if not clientes:
            raise HTTPException(
                status_code=503,
                detail="No hay ningun proveedor LLM configurado.",
            )

        if proveedor_preferido:
            alias = proveedor_preferido.lower().strip()
            valor_proveedor = self._ALIAS_PROVEEDOR.get(alias)
            if valor_proveedor is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Proveedor desconocido: '{proveedor_preferido}'. "
                           f"Valores validos: {list(self._ALIAS_PROVEEDOR.keys())}",
                )
            candidatos = [c for c in clientes if c.proveedor.value == valor_proveedor]
            if not candidatos:
                raise HTTPException(
                    status_code=503,
                    detail=f"El proveedor '{proveedor_preferido}' no esta disponible "
                           f"(clave de API no configurada).",
                )
        else:
            # Orden de coste ascendente: Gemini < Grok < GPT-4o < Claude.
            _orden_coste = {"google": 0, "xai": 1, "openai": 2, "anthropic": 3}
            candidatos = sorted(clientes, key=lambda c: _orden_coste.get(c.proveedor.value, 9))

        prompt_generacion = (
            "Genera un texto en español de un minimo de 310 palabras y un maximo de 390 palabras "
            "sobre un tema de cultura general, ciencia, historia, naturaleza o sociedad. "
            "El texto debe ser coherente, fluido y adecuado para ser resumido. "
            "No incluyas titulo, subtitulos ni listas. Solo parrafos de texto corrido. "
            "Varia el tema con cada generacion para que nunca se repita el mismo asunto. "
            "Devuelve unicamente el texto, sin comentarios ni explicaciones adicionales."
        )
        # Umbral minimo aceptable: 5 palabras de margen sobre el minimo del frontend (300)
        _MIN_PALABRAS = 305

        ultimo_error: str = "Error desconocido"
        for cliente in candidatos:
            try:
                resultado = await cliente.completar(prompt_generacion, max_tokens=700)
                if not resultado.tuvo_error and resultado.texto_respuesta:
                    texto = resultado.texto_respuesta.strip()
                    palabras = len(texto.split())

                    # Si el LLM no alcanzo el minimo, un segundo intento mas directo
                    if palabras < _MIN_PALABRAS:
                        logger.info(
                            "Texto de ejemplo demasiado corto (%d palabras) con %s — reintentando.",
                            palabras, cliente.proveedor,
                        )
                        prompt_ampliar = (
                            f"El siguiente texto solo tiene {palabras} palabras. "
                            "Amplíalo hasta alcanzar al menos 310 palabras manteniendo la coherencia y el estilo. "
                            "Devuelve únicamente el texto completo ampliado, sin comentarios adicionales.\n\n"
                            + texto
                        )
                        resultado2 = await cliente.completar(prompt_ampliar, max_tokens=800)
                        if not resultado2.tuvo_error and resultado2.texto_respuesta:
                            texto = resultado2.texto_respuesta.strip()
                            palabras = len(texto.split())

                    return RespuestaTextoEjemplo(
                        texto=texto,
                        palabras=palabras,
                        proveedor=cliente.proveedor.value,
                    )
                ultimo_error = resultado.mensaje_error or "El LLM no devolvio texto."
            except Exception as exc:
                ultimo_error = str(exc)
                logger.warning("Error generando texto de ejemplo con %s: %s", cliente.proveedor, exc)

        raise HTTPException(
            status_code=503,
            detail=f"No se pudo generar el texto de ejemplo: {ultimo_error}",
        )
