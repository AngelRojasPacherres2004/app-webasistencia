-- Ejecutar en Supabase SQL Editor para permitir jornadas sin receso.
BEGIN;
ALTER TABLE public.horario_trabajador DROP CONSTRAINT IF EXISTS horario_trabajador_orden_valido;
ALTER TABLE public.horario_trabajador ADD CONSTRAINT horario_trabajador_orden_valido CHECK (
    horario_entrada IS NOT NULL AND horario_salida IS NOT NULL
    AND horario_entrada < horario_salida
    AND (
        (horario_inicio_receso IS NULL AND horario_fin_receso IS NULL)
        OR (horario_inicio_receso IS NOT NULL AND horario_fin_receso IS NOT NULL
            AND horario_entrada <= horario_inicio_receso
            AND horario_inicio_receso < horario_fin_receso
            AND horario_fin_receso <= horario_salida)
    )
);
COMMIT;
