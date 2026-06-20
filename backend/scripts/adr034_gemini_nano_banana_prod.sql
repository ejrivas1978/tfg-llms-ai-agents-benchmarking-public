-- =============================================================================
-- ADR-034 — Gemini imagen generativa: Imagen 4 -> gemini-2.5-flash-image (Nano Banana)
-- =============================================================================
-- Ejecutar en la BD de PRODUCCION (Cloud SQL) UNA vez.
-- Equivale al ajuste ya aplicado en local el 05/06/2026.
--
-- Es IDEMPOTENTE: re-ejecutarlo no causa danos (los WHERE solo tocan filas que
-- aun esten en el estado antiguo).
--
-- El backfill es necesario porque el coste del dashboard se lee del cost_usd
-- guardado en cada llm_responses; NO se recalcula desde la tarifa vigente.
--
-- Las filas de llm_responses se filtran por model_name (no por provider) para
-- evitar tocar respuestas de texto que pudieran costar 0.04 por casualidad.
-- =============================================================================

BEGIN;

-- 1) Tarifa vigente de Gemini: precio_imagen_generar 0.04 -> 0.039
--    En la misma fila vigente, SIN versionar una tarifa nueva (ADR-034).
UPDATE tarifas_llm
SET precio_imagen_generar_usd_por_imagen = 0.039,
    actualizado_por = 'ajuste-nano-banana',
    actualizado_en  = NOW()
WHERE proveedor = 'gemini'
  AND vigente IS TRUE
  AND precio_imagen_generar_usd_por_imagen = 0.04;

-- 2) Backfill de costes: 0.04 -> 0.039 en las imagenes de Gemini ya generadas
--    (cubre tanto las antiguas de Imagen 4 como la edicion con Nano Banana).
UPDATE llm_responses
SET cost_usd = 0.039
WHERE model_name IN ('imagen-4.0-generate-001', 'gemini-2.5-flash-image')
  AND cost_usd = 0.04;

-- 3) Homogeneizar el modelo: imagen-4.0-generate-001 -> gemini-2.5-flash-image
--    (las fallidas, con cost_usd = 0, tambien se renombran; su coste sigue 0).
UPDATE llm_responses
SET model_name = 'gemini-2.5-flash-image'
WHERE model_name = 'imagen-4.0-generate-001';

COMMIT;

-- =============================================================================
-- VERIFICACION (ejecutar tras el COMMIT; deben dar los resultados esperados)
-- =============================================================================
-- a) No debe quedar ninguna fila con el modelo antiguo:
--    SELECT COUNT(*) AS quedan_imagen4 FROM llm_responses
--    WHERE model_name = 'imagen-4.0-generate-001';   -- esperado: 0
--
-- b) Tarifa vigente de Gemini igualada a 0.039 en ambas columnas:
--    SELECT precio_imagen_generar_usd_por_imagen, precio_imagen_editar_usd_por_imagen
--    FROM tarifas_llm WHERE proveedor = 'gemini' AND vigente IS TRUE;
--
-- c) Costes de imagen de Gemini ya homogeneos (las exitosas a 0.039):
--    SELECT model_name, cost_usd, tuvo_error, COUNT(*)
--    FROM llm_responses WHERE model_name = 'gemini-2.5-flash-image'
--    GROUP BY model_name, cost_usd, tuvo_error ORDER BY cost_usd;
-- =============================================================================
