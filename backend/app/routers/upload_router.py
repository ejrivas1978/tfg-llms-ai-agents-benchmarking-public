"""
Modulo: routers.upload_router
Ruta:   backend/app/routers/upload_router.py

Descripcion:
    Endpoint de extraccion de texto desde ficheros (.txt, .pdf, .docx).
    Usado por la categoria resumen del benchmarking para cargar documentos
    sin tener que copiar y pegar el contenido manualmente.

    Endpoints:
        POST /api/v1/upload/extraer-texto -> TextoExtraido  200

Limites:
    - Tamano maximo de fichero: 10 MB
    - Palabras maximas en la respuesta: 8000 (el resto se trunca)
    - Formatos soportados: .txt, .pdf, .docx

Sprint: Sprint 4
"""

import io
import logging
from typing import Annotated

import docx
import pdfplumber
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

logger = logging.getLogger(__name__)

LIMITE_PALABRAS: int = 8_000
LIMITE_BYTES: int    = 10 * 1024 * 1024  # 10 MB
EXTENSIONES_PERMITIDAS: set[str] = {".txt", ".pdf", ".docx"}

router = APIRouter(prefix="/upload", tags=["utilidades"])


class TextoExtraido(BaseModel):
    """Respuesta del endpoint de extraccion de texto.

    Atributos:
        texto:    Contenido extraido del fichero, truncado si supera el limite.
        palabras: Numero de palabras del texto devuelto.
        truncado: True si el fichero supero el limite y se recorto.
    """

    texto:    str
    palabras: int
    truncado: bool


def _truncar(texto: str, limite: int) -> tuple[str, bool]:
    """Recorta el texto al numero maximo de palabras.

    Args:
        texto:  Texto completo extraido.
        limite: Numero maximo de palabras.

    Returns:
        Tupla (texto_resultante, fue_truncado).
    """
    palabras = texto.split()
    if len(palabras) <= limite:
        return texto, False
    return " ".join(palabras[:limite]), True


def _extraer_txt(contenido: bytes) -> str:
    """Decodifica un fichero de texto plano probando encodings habituales.

    Args:
        contenido: Bytes del fichero.

    Returns:
        Texto decodificado.

    Raises:
        HTTPException 422: si ninguna codificacion funciona.
    """
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            return contenido.decode(enc)
        except UnicodeDecodeError:
            continue
    raise HTTPException(
        status_code=422,
        detail="No se pudo decodificar el fichero. Guarda el .txt en UTF-8.",
    )


def _extraer_pdf(contenido: bytes) -> str:
    """Extrae texto de un PDF con pdfplumber.

    Args:
        contenido: Bytes del fichero PDF.

    Returns:
        Texto de todas las paginas concatenado.

    Raises:
        HTTPException 422: si el PDF esta protegido o no contiene texto.
    """
    try:
        with pdfplumber.open(io.BytesIO(contenido)) as pdf:
            partes = [pagina.extract_text() or "" for pagina in pdf.pages]
        return "\n".join(partes).strip()
    except Exception as exc:
        logger.warning("Error extrayendo PDF: %s", exc)
        raise HTTPException(
            status_code=422,
            detail="No se pudo extraer texto del PDF. Comprueba que no esta protegido con contrasena.",
        )


def _extraer_docx(contenido: bytes) -> str:
    """Extrae texto de un fichero .docx con python-docx.

    Args:
        contenido: Bytes del fichero DOCX.

    Returns:
        Texto de todos los parrafos concatenado.

    Raises:
        HTTPException 422: si el fichero esta corrupto o no es un DOCX valido.
    """
    try:
        documento = docx.Document(io.BytesIO(contenido))
        parrafos = [p.text for p in documento.paragraphs if p.text.strip()]
        return "\n".join(parrafos)
    except Exception as exc:
        logger.warning("Error extrayendo DOCX: %s", exc)
        raise HTTPException(
            status_code=422,
            detail="No se pudo leer el fichero Word. Comprueba que es un .docx valido.",
        )


@router.post(
    "/extraer-texto",
    response_model=TextoExtraido,
    summary="Extrae texto de un fichero .txt, .pdf o .docx",
    description=(
        "Recibe un fichero y devuelve su contenido como texto plano. "
        f"Maximo {LIMITE_PALABRAS} palabras; si el fichero es mas largo se trunca "
        "y se indica con el flag truncado=True."
    ),
)
async def extraer_texto(
    archivo: Annotated[UploadFile, File(description="Fichero .txt, .pdf o .docx (max 10 MB)")],
) -> TextoExtraido:
    """Extrae y devuelve el texto de un fichero subido por el usuario.

    Args:
        archivo: Fichero enviado como multipart/form-data.

    Returns:
        TextoExtraido con el contenido, numero de palabras y flag de truncado.

    Raises:
        HTTPException 413: fichero supera el limite de tamano.
        HTTPException 415: extension no soportada.
        HTTPException 422: fichero corrupto o sin texto extraible.
    """
    nombre    = archivo.filename or ""
    extension = ("." + nombre.rsplit(".", 1)[-1].lower()) if "." in nombre else ""

    if extension not in EXTENSIONES_PERMITIDAS:
        raise HTTPException(
            status_code=415,
            detail=f"Formato no soportado. Formatos validos: {', '.join(sorted(EXTENSIONES_PERMITIDAS))}",
        )

    contenido = await archivo.read()

    if len(contenido) > LIMITE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"El fichero supera el limite de {LIMITE_BYTES // (1024 * 1024)} MB.",
        )

    if extension == ".txt":
        texto_bruto = _extraer_txt(contenido)
    elif extension == ".pdf":
        texto_bruto = _extraer_pdf(contenido)
    else:
        texto_bruto = _extraer_docx(contenido)

    if not texto_bruto.strip():
        raise HTTPException(
            status_code=422,
            detail="El fichero no contiene texto extraible.",
        )

    texto_final, truncado = _truncar(texto_bruto, LIMITE_PALABRAS)

    return TextoExtraido(
        texto=texto_final,
        palabras=len(texto_final.split()),
        truncado=truncado,
    )
