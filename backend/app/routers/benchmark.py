"""
Modulo: routers.benchmark
Ruta:   backend/app/routers/benchmark.py

Descripcion:
    Capa HTTP para los endpoints publicos de benchmark.
    Los usuarios anonimos solo necesitan su nickname para lanzar y consultar evaluaciones.
    Los routers no contienen logica de negocio: delegan completamente en BenchmarkService.

    Endpoints:
        POST /api/v1/benchmarks/run              -> RespuestaBenchmark  201
        GET  /api/v1/benchmarks/{id}             -> RespuestaBenchmark  200
        GET  /api/v1/benchmarks/historial/{nick} -> list[ResumenEvaluacionUsuario]  200
        GET  /api/v1/benchmarks/imagen/descargar -> Response (imagen binaria)

    Seguridad:
        - Rate limiting en endpoints publicos de lectura para prevenir enumeracion masiva.
        - Validacion anti-SSRF en el proxy de imagen: solo HTTPS con hostname publico.
        - JWT opcional en historial: si hay JWT valido, el nick debe coincidir con el
          usuario autenticado (los admins pueden consultar cualquier nick).

Dependencias:
    - fastapi
    - app.core.database
    - app.schemas.benchmark
    - app.services.benchmark_service

Sprint: Sprint 2 / Sprint 5 (seguridad)
"""

import ipaddress
import httpx
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_actor_benchmark, get_usuario_opcional
from app.middleware.rate_limit import limitador
from app.models.usuario_app import UsuarioApp
from app.repositories.benchmark_evaluacion_repository import BenchmarkEvaluacionRepository
from app.schemas.benchmark import (
    PeticionBenchmark,
    ResumenEvaluacionUsuario,
    RespuestaBenchmark,
    RespuestaTextoEjemplo,
)
from app.services.benchmark_service import BenchmarkService

# Hostnames y sufijos de dominio bloqueados para prevenir SSRF.
# Cloud Run expone el servicio de metadatos en 169.254.169.254 y en
# metadata.google.internal; ambos deben ser inaccesibles desde el proxy.
_HOSTNAMES_BLOQUEADOS: frozenset[str] = frozenset({
    "localhost",
    "metadata.google.internal",
})
_SUFIJOS_INTERNOS: tuple[str, ...] = (".local", ".internal", ".corp", ".lan", ".intranet")


def _validar_url_imagen(url: str) -> None:
    """Valida que la URL es segura para proxiar (anti-SSRF).

    Rechaza:
      - Esquemas distintos de HTTPS (HTTP en claro expone la red interna).
      - URLs con direccion IP literal (IPv4 o IPv6), incluidas las de
        metadatos de cloud (169.254.169.254) y loopback (127.0.0.1).
      - Hostnames internos conocidos y sufijos de red privada.

    Args:
        url: URL candidata a proxiar.

    Raises:
        HTTPException 400: si la URL no supera alguna de las comprobaciones.
    """
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se admiten URLs HTTPS para la descarga de imagenes",
        )
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL sin hostname valido",
        )
    # Rechazar IPs literales (IPv4 e IPv6)
    try:
        ipaddress.ip_address(hostname)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URLs con direcciones IP no permitidas",
        )
    except ValueError:
        pass  # Es un hostname, no una IP — continuar
    if hostname in _HOSTNAMES_BLOQUEADOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Host no permitido",
        )
    if any(hostname.endswith(sfx) for sfx in _SUFIJOS_INTERNOS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Host interno no permitido",
        )

router = APIRouter(prefix="/benchmarks", tags=["benchmark"])


@router.post(
    "/run",
    response_model=RespuestaBenchmark,
    status_code=status.HTTP_201_CREATED,
    summary="Ejecutar una evaluacion de benchmark",
    description=(
        "Envia el prompt a todos los proveedores LLM configurados en paralelo. "
        "Requiere autenticacion: JWT de usuario web (cuota controlada) o de administrador (ilimitado). "
        "Los errores y rechazos por politica de contenido no consumen cuota. "
        "Limite: 5 peticiones por minuto por IP."
    ),
)
@limitador.limit("5/minute")
async def ejecutar_benchmark(
    request: Request,
    peticion: PeticionBenchmark,
    db: AsyncSession = Depends(get_db),
    usuario_app: UsuarioApp | None = Depends(get_actor_benchmark),
) -> RespuestaBenchmark:
    """Lanza un benchmark con el prompt y categoria indicados.

    Args:
        peticion: Datos de la evaluacion (nickname, prompt, categoria).
        db: Sesion de base de datos asincrona.
        usuario_app: UsuarioApp autenticado o None si es administrador.

    Returns:
        RespuestaBenchmark con la evaluacion y las respuestas de todos los LLMs.
    """
    servicio = BenchmarkService(db)
    return await servicio.ejecutar(
        nickname=peticion.nickname,
        prompt=peticion.prompt,
        categoria=peticion.categoria,
        imagen_base64=peticion.imagen_base64,
        imagen_mime_type=peticion.imagen_mime_type,
        subcat_imagen=peticion.subcat_imagen,
        subcategoria_csv=peticion.subcategoria_csv,
        usuario_app=usuario_app,
        prompt_en=peticion.prompt_en,
        texto_entrada=peticion.texto_entrada,
        texto_entrada_autogenerado=peticion.texto_entrada_autogenerado,
    )


@router.get(
    "/texto-ejemplo",
    response_model=RespuestaTextoEjemplo,
    summary="Generar texto de ejemplo para la categoria resumen",
    description=(
        "Genera un texto en castellano de ~300 palabras sobre un tema aleatorio. "
        "Si se indica 'proveedor', usa ese LLM concreto; si no, usa el primero disponible. "
        "No persiste nada en base de datos ni consume cuota. Requiere autenticacion. "
        "Limite: 10 peticiones por minuto."
    ),
)
@limitador.limit("10/minute")
async def generar_texto_ejemplo(
    request: Request,
    proveedor: str | None = Query(
        None,
        description="Proveedor LLM a usar: 'claude', 'openai', 'gemini' o 'grok'. "
                    "Si se omite, se usa el primero disponible.",
    ),
    db: AsyncSession = Depends(get_db),
    usuario_app: UsuarioApp | None = Depends(get_actor_benchmark),
) -> RespuestaTextoEjemplo:
    """Genera un texto de ~300 palabras para rellenar el panel de resumen.

    Args:
        request: Peticion HTTP (requerida por el limitador de tasa).
        proveedor: Nombre del proveedor LLM deseado (opcional).
        db: Sesion de base de datos asincrona.
        usuario_app: UsuarioApp autenticado (admin o usuario web habilitado).

    Returns:
        RespuestaTextoEjemplo con el texto generado, el recuento de palabras y el proveedor.
    """
    servicio = BenchmarkService(db)
    return await servicio.generar_texto_ejemplo(proveedor_preferido=proveedor)


@router.get(
    "/historial/{nick}",
    response_model=list[ResumenEvaluacionUsuario],
    summary="Historial de evaluaciones de un evaluador",
    description=(
        "Devuelve las ultimas 50 evaluaciones del nick indicado, ordenadas "
        "por fecha descendente, con el flag evaluada calculado en BD. "
        "No requiere autenticacion: el historial es de lectura publica para "
        "que el frontend lo cargue aunque el JWT haya expirado. "
        "Si hay JWT valido de otro usuario (no admin), devuelve 403. "
        "Limite: 20 peticiones por minuto por IP."
    ),
)
@limitador.limit("20/minute")
async def historial_por_nick(
    nick: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    usuario_actual: UsuarioApp | None = Depends(get_usuario_opcional),
) -> list[ResumenEvaluacionUsuario]:
    """Recupera el historial de evaluaciones del nick indicado desde BD.

    Si hay un JWT valido en la peticion y el usuario autenticado no es
    admin ni el propietario del nick solicitado, se rechaza con 403.
    Esto impide que un usuario autenticado use la API para consultar
    el historial de otro usuario. Las peticiones sin JWT (o con JWT
    expirado) continuan teniendo acceso publico para compatibilidad
    con el flujo de historial cuando el token ha caducado.

    Args:
        nick: Alias del evaluador cuyo historial se solicita.
        request: Peticion HTTP (requerida por el limitador de tasa).
        db: Sesion de base de datos asincrona.
        usuario_actual: UsuarioApp si el JWT es valido, None si no hay token.

    Returns:
        Lista de ResumenEvaluacionUsuario con las ultimas 50 evaluaciones.

    Raises:
        HTTPException 403: JWT valido de un usuario distinto al nick solicitado.
    """
    if (
        usuario_actual is not None
        and not usuario_actual.is_admin
        and usuario_actual.nick.lower() != nick.lower()
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puedes consultar el historial de otro usuario.",
        )

    repo = BenchmarkEvaluacionRepository(db)
    pares = await repo.listar_historial_usuario(nickname=nick, limite=50)
    return [
        ResumenEvaluacionUsuario(
            id=ev.id,
            prompt=ev.prompt,
            categoria=ev.category,
            estado=ev.status,
            created_at=ev.created_at,
            evaluada=evaluada,
        )
        for ev, evaluada in pares
    ]


@router.get(
    "/{evaluacion_id}",
    response_model=RespuestaBenchmark,
    summary="Obtener una evaluacion de benchmark por ID",
    description=(
        "Devuelve una evaluacion de benchmark con todas sus respuestas LLM y metricas. "
        "No requiere autenticacion. Limite: 30 peticiones por minuto por IP."
    ),
)
@limitador.limit("30/minute")
async def obtener_evaluacion(
    evaluacion_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> RespuestaBenchmark:
    """Recupera una evaluacion de benchmark con todas sus respuestas.

    Args:
        evaluacion_id: ID de la evaluacion a recuperar.
        request: Peticion HTTP (requerida por el limitador de tasa).
        db: Sesion de base de datos asincrona.

    Returns:
        RespuestaBenchmark con la evaluacion y sus respuestas LLM.
    """
    servicio = BenchmarkService(db)
    return await servicio.obtener_por_id(evaluacion_id)


@router.get(
    "/imagen/descargar",
    summary="Proxy de descarga de imagen generada (solo HTTPS con host publico)",
    description=(
        "Descarga la imagen desde la URL HTTPS del proveedor y la reenvía al cliente. "
        "Resuelve las restricciones CORS de los CDN de OpenAI y Grok. "
        "Las imagenes Gemini (data-URI base64) se descargan directamente desde el frontend. "
        "La URL debe ser HTTPS con hostname publico (sin IPs ni dominios internos)."
    ),
)
async def descargar_imagen(
    url: str = Query(..., description="URL HTTPS de la imagen a descargar"),
) -> Response:
    """Hace de proxy entre el cliente y el CDN del proveedor LLM.

    Valida la URL con _validar_url_imagen antes de realizar la peticion
    para prevenir ataques SSRF que intenten acceder a recursos internos
    de la red de Cloud Run (metadatos, servicios internos).

    Args:
        url: URL HTTPS de la imagen generada por el proveedor.

    Returns:
        Response con el contenido binario de la imagen lista para descargar.

    Raises:
        HTTPException 400: URL no valida (no HTTPS, IP literal, host interno).
        HTTPException 502: error al contactar con el CDN del proveedor.
    """
    _validar_url_imagen(url)

    try:
        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; TFG-LLM-Benchmark/1.0)"},
        ) as cliente:
            respuesta = await cliente.get(url)
            respuesta.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"No se pudo obtener la imagen: {exc}") from exc

    content_type = respuesta.headers.get("content-type", "image/png")
    return Response(
        content=respuesta.content,
        media_type=content_type,
        headers={"Content-Disposition": "attachment; filename=imagen-generada.png"},
    )
