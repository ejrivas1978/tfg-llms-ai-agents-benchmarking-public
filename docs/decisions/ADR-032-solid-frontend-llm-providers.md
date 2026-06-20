# ADR-032: SOLID en el frontend — llmProviders.ts como fuente única de verdad

Estado: Aceptado
Fecha: 17/05/2026
Sprint: Sprint 4

## Contexto

El frontend acumuló metadatos de proveedores LLM dispersos en seis o más componentes: colores hardcodeados como strings hex en estilos inline, arrays locales con los cuatro nombres, lógica de inactivación basada en comprobaciones `proveedor === 'claude'`, etc. Añadir un quinto proveedor habría requerido localizar y modificar cada uno de esos puntos, con alto riesgo de inconsistencia visual y de comportamiento.

El mismo problema afectaba a los tokens de diseño: valores hex repetidos en decenas de componentes sin ninguna relación declarada con el sistema de diseño de Tailwind.

## Opciones consideradas

1. **Mantener el estado actual** — sencillo a corto plazo, pero cada nuevo proveedor o cambio de color multiplica el número de ficheros a modificar.
2. **Centralizar en un fichero de configuración + tokens programáticos** — requiere una refactorización de todos los componentes afectados, pero aplica el principio Open/Closed y convierte la adición de un proveedor en una operación acotada a tres ficheros.
3. **Usar Context API de React para los metadatos de proveedor** — evita la importación directa pero introduce indirección innecesaria para datos que son estáticos en tiempo de ejecución.

## Decisión tomada

Se elige la opción 2. Se crean dos módulos nuevos:

- **`frontend/src/config/llmProviders.ts`**: define la interfaz `ProveedorConfig` y el objeto `LLM_PROVIDERS_CONFIG` indexado por `LLMProvider`. Expone constantes derivadas (`PROVEEDORES_LIST`, `PROVEEDORES_SIN_IMAGEN`) y helpers (`proveedorColor`, `proveedorIcono`, `proveedorNombre`). Todos los componentes consumen este módulo en lugar de declarar sus propios valores.

- **`frontend/src/utils/tokens.ts`**: objeto `TOKENS` con los 28 tokens de diseño del sistema para uso programático (canvas, Recharts, Mermaid). Para CSS declarativo se siguen usando las clases Tailwind.

El union type `LLMProvider` en `types/benchmark.ts` actúa como fuente de verdad para los identificadores válidos. TypeScript garantiza en tiempo de compilación que `LLM_PROVIDERS_CONFIG` tiene exactamente una entrada por cada valor del union.

## Consecuencias

Positivas:
- Añadir un quinto proveedor requiere cambios en exactamente tres ficheros (`types/benchmark.ts`, `utils/llmIcons.ts`, `config/llmProviders.ts`). Ningún componente se modifica.
- La UI es consistente por construcción: un cambio de color en `llmProviders.ts` se propaga a chips, tarjetas, gráficas y filtros sin búsqueda manual.
- Los flags de capacidad (`puedeGenerarImagenes`, `puedeVision`) eliminan los condicionales hardcodeados en `SubcatPanel` y similares.

Trade-offs asumidos:
- Requiere una refactorización puntual de todos los componentes afectados. Costo: una sesión de trabajo.
- Los colores de proveedor en `llmProviders.ts` deben mantenerse sincronizados manualmente con `tailwind.config.ts` si se añaden clases Tailwind por proveedor.

Riesgos:
- Ninguno identificado. TypeScript verifica en compilación que `LLM_PROVIDERS_CONFIG` es exhaustivo respecto al union type.
