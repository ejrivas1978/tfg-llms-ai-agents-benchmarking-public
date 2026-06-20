"""
Modulo: base_client
Ruta:   backend/app/llm_engine/clients/base_client.py

Descripcion:
    Clase base abstracta para todos los clientes LLM.
    Define el contrato que deben cumplir los cuatro clientes concretos
    y centraliza la logica de utilidad comun (tiempo de latencia).

    DECISION(ADR-003): He aplicado el patron de interfaz abstracta (ABC) para que
    el runner y el servicio dependan de BaseLLMClient y no de implementaciones
    concretas. Esto me permite sustituir cualquier cliente por un mock en los
    tests sin cambiar el codigo del runner, y anadir nuevos proveedores
    simplemente creando una nueva subclase sin tocar el resto del sistema.

Sprint: Sprint 2
"""

import time
from abc import ABC, abstractmethod

from app.llm_engine.resultado import ResultadoLLM
from app.models.enums import LLMProvider


class BaseLLMClient(ABC):
    """Interfaz abstracta para los clientes LLM del benchmark.

    He decidido definir tres flags de capacidades (SOPORTA_IMAGEN, SOPORTA_VISION,
    SOPORTA_EDICION_IMAGEN) como atributos de clase en lugar de metodos abstractos.
    La razon es que el runner necesita filtrar clientes antes de crear las coroutines,
    y consultar un atributo de clase es mas sencillo que llamar a un metodo.

    La implementacion por defecto de generar_imagen() y editar_imagen() devuelve
    un error en lugar de lanzar NotImplementedError. He tomado esta decision para
    que los clientes que no soporten imagen devuelvan un ResultadoLLM(tuvo_error=True)
    coherente con el resto de respuestas, en lugar de romper el asyncio.gather.

    Atributos de clase:
        SOPORTA_IMAGEN: True si el cliente implementa generar_imagen() de verdad.
        SOPORTA_VISION: True si completar() acepta imagen_base64 para vision.
        SOPORTA_EDICION_IMAGEN: True si editar_imagen() usa la API nativa de edicion.
    """

    SOPORTA_IMAGEN: bool = False
    SOPORTA_VISION: bool = True
    SOPORTA_EDICION_IMAGEN: bool = False

    def __init__(self, api_key: str, modelo: str, proveedor: LLMProvider) -> None:
        """Inicializa el cliente con credenciales y nombre de modelo.

        He guardado api_key como atributo protegido (_api_key) porque GeminiClient
        necesita pasarla como parametro de query en la REST API de Imagen 4,
        donde el SDK de OpenAI no la inyecta automaticamente en el encabezado.

        Args:
            api_key: Clave de API del proveedor. Nunca se loguea.
            modelo: Identificador exacto del modelo (ej: claude-sonnet-4-6).
            proveedor: Enum LLMProvider para etiquetar los resultados en BB.DD.
        """
        self._api_key = api_key
        self._modelo = modelo
        self._proveedor = proveedor

    @property
    def proveedor(self) -> LLMProvider:
        """Expone el proveedor de solo lectura para que el runner pueda consultarlo."""
        return self._proveedor

    @abstractmethod
    async def completar(
        self,
        prompt: str,
        max_tokens: int = 2048,
        imagen_base64: str | None = None,
        imagen_mime_type: str | None = None,
    ) -> ResultadoLLM:
        """Envia el prompt al LLM y devuelve el resultado con metricas calculadas.

        He marcado este metodo como abstracto porque es el nucleo de cada cliente:
        cada proveedor tiene una API diferente y no puedo dar una implementacion
        por defecto razonable. Las subclases deben implementarlo.

        Invariante de diseno: este metodo NUNCA lanza excepciones al llamador.
        Los errores de red y de API se capturan dentro de cada implementacion
        y se devuelven como ResultadoLLM(tuvo_error=True). Esto permite que
        asyncio.gather con return_exceptions=True reciba siempre un ResultadoLLM,
        no una mezcla de resultados y excepciones.

        Args:
            prompt: Texto del prompt enviado al modelo.
            max_tokens: Limite de tokens en la respuesta generada.
            imagen_base64: Datos de la imagen en base64, sin el prefijo data-URI.
            imagen_mime_type: MIME type de la imagen (ej. image/jpeg).

        Returns:
            ResultadoLLM con todas las metricas calculadas o con tuvo_error=True.
        """
        ...

    async def generar_imagen(self, prompt: str) -> ResultadoLLM:
        """Genera una imagen a partir del prompt. Solo disponible si SOPORTA_IMAGEN=True.

        He puesto una implementacion por defecto que devuelve un error en lugar
        de dejar el metodo abstracto. La razon es que el runner comprueba
        SOPORTA_IMAGEN antes de llamar a este metodo, asi que en condiciones
        normales ClaudeClient nunca llega aqui. Pero si por un bug se llamara,
        prefiero un mensaje de error claro a un AttributeError o NotImplementedError.

        Args:
            prompt: Descripcion textual de la imagen a generar.

        Returns:
            ResultadoLLM(tuvo_error=True) con mensaje explicativo.
        """
        return ResultadoLLM(
            proveedor=self._proveedor,
            modelo=self._modelo,
            tuvo_error=True,
            mensaje_error=f"{type(self).__name__} no soporta generacion de imagenes",
            es_imagen=True,
        )

    async def editar_imagen(
        self,
        prompt: str,
        imagen_base64: str,
        imagen_mime_type: str,
    ) -> ResultadoLLM:
        """Edita una imagen aplicando las instrucciones del prompt.

        He puesto como implementacion por defecto una delegacion a generar_imagen()
        para los clientes sin soporte nativo de edicion (Gemini, Grok). Estos
        clientes generan una imagen nueva a partir del prompt de instruccion,
        ignorando la imagen de referencia. Es una aproximacion imperfecta pero
        permite que el benchmark funcione con cuatro proveedores en lugar de uno.

        Solo OpenAIClient (con SOPORTA_EDICION_IMAGEN=True) sobreescribe este metodo
        para usar la API real de edicion de gpt-image-1 con imagen de referencia.

        He extraido el prefijo estandar del prompt antes de pasar la instruccion
        a generar_imagen(), porque el formato 'Modifica la imagen adjunta aplicando...'
        incluye contexto sobre la imagen que no tiene sentido para un modelo de
        generacion pura sin acceso a esa imagen.

        Args:
            prompt: Instruccion de modificacion con el prefijo estandar incluido.
            imagen_base64: Imagen de referencia (ignorada en esta implementacion base).
            imagen_mime_type: MIME type de la imagen (ignorado en esta implementacion).

        Returns:
            ResultadoLLM con imagen generada (no editada), o tuvo_error=True.
        """
        # Extraer solo la instruccion del usuario, sin el prefijo estandar de modificacion.
        # El prefijo lo añade benchmark_service.py al construir el prompt de edicion.
        _PREFIJO = "Modifica la imagen adjunta aplicando el siguiente cambio: "
        instruccion = prompt[len(_PREFIJO):] if prompt.startswith(_PREFIJO) else prompt
        return await self.generar_imagen(instruccion)

    def _marca_inicio(self) -> float:
        """Devuelve el tiempo monotono actual para calcular latencia.

        Uso time.monotonic() en lugar de time.time() porque monotonic no puede
        retroceder (no le afectan cambios de NTP ni ajustes de reloj del sistema),
        lo que garantiza que la latencia calculada sea siempre un valor positivo.
        """
        return time.monotonic()

    def _latencia_ms(self, inicio: float) -> int:
        """Calcula la latencia en milisegundos desde el inicio dado."""
        return int((time.monotonic() - inicio) * 1000)
