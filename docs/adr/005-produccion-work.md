# ADR 005 · Producción completa en WORK
El encargo continúa después de validar la fase 01. Se conserva su API y su ficha. El piloto sirve de entrada a una producción independiente. Antes de migrar datos vivos se hará una copia local verificable.

| Fase | Decisión | Prueba de salida |
|---|---|---|
| 02 | Roles deterministas con presupuestos y esquemas. Versionar guion y storyboard. Ningún acceso a modelos en WORK. | Mismo input y versión producen el mismo plan; datos inválidos y referencias cruzadas se rechazan. |
| 03 | Proveedor geométrico propio, audio sintetizado, FFmpeg y ffprobe locales. Planos y montaje por hash. | Descargar un reel de 20 s, cinco planos, portada, subtítulos, copy, timeline y manifest; inspeccionar streams y sonido. |
| 04 | Checkpoints de CPU en SQL y un worker local con exclusión de proceso. Editar un plano invalida el montaje y su aprobación. | Recuperar tras cierre, cancelar, comparar candidatos, aplicar límites, reanudar eventos y verificar revisión por hash. |
| 05 | Registrar exclusivamente programación y ejecución dry-run por marca. | Aprobación humana explícita, idempotencia, límite local por día y métricas claramente simuladas. |
| 06 | Preparar diagnóstico portátil, contratos para servidores loopback y protocolo de benchmark. | Medición real exclusivamente en HOME tras comprobar hardware, licencia y autorización de descargas. |
| 07 | Pruebas locales, copia coherente y restauración a directorio nuevo. | Reabrir base y validar hashes; conservar los datos previos del piloto. |

Temporal, LangGraph y psycopg siguen ausentes. La alternativa en WORK es un productor determinista y una cola SQL persistente que confirma cada plano antes del siguiente. Una interrupción puede repetir cómputo del plano en curso. Las asociaciones visibles se confirman transaccionalmente. La actividad se observa en local. La publicación real y los drivers permanecen fuera del ejecutable WORK.
