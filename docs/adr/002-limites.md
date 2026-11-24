# ADR 002 · Límites de ejecución
Aceptada para la fase 01 el 24-11-2026.

Perfil efectivo WORK, cero jobs GPU, un usuario local de confianza. Configuración operativa pequeña y validada al arrancar. El YAML suministrado describe perfiles futuros. No habilitar publicación, investigación, inferencia, descargas, telemetría ni enlaces a código de terceros en el navegador. El sistema operativo y procesos con acceso al directorio de datos forman parte de la frontera de confianza.

Un job manual genera una ficha de campaña con datos introducidos por el operador. La ejecución es síncrona y acotada. SQLite serializa la escritura y PostgreSQL bloquea los registros implicados. El resultado se direcciona por SHA-256; primero se guarda el contenido completo, después se confirma la referencia. Un fallo anterior al commit puede dejar un blob sin referencia. No ejecutar limpieza automática. Tras interrupción se puede volver a solicitar la operación. No hay worker durable, heartbeats, reintentos automáticos ni SLA. Temporal queda para actividades largas en una fase posterior.

En HOME comprobar equipo, RAM real, VRAM libre y espacio antes de elegir perfil. Un solo proceso de inferencia GPU. Cualquier peso o asset importado requiere procedencia y licencia verificadas para el uso previsto. Fase 01 solo admite texto del operador y metadatos internos; no permite importar medios ni aprobarlos para uso comercial.

### Sustitución del ejecutor

El adaptador ManualBriefExecutor acepta una instantánea de marca y campaña y devuelve el hash después de escribir los bytes. Para incorporar Temporal, versionar el tipo de job, persistir en una transacción la instantánea de entrada y la orden de encolado, y usar el UUID del job como ID del workflow. Una actividad escribe el blob por hash y confirma su referencia de forma idempotente. Probar caída antes y después del commit, reanudación sin duplicados y cancelación antes de cambiar el adaptador predeterminado. El cliente actual recibe el resultado de la ejecución síncrona; aplicar una nueva versión del contrato si se introduce aceptación asíncrona.
