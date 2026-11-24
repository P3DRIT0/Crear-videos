# ADR 004 · Entregas y puertas de aceptación
Aceptada el 24-11-2026. Solo se ejecuta 01.

| Fase | Entrega | Criterio para avanzar |
|---|---|---|
| 01 · Núcleo | Dashboard, API, configuración WORK, almacenamiento, migración, CRUD | Crear campaña y job, ejecutar, abrir ficha por ID y comprobar hash; reiniciar y recuperar datos. Probar entradas inválidas, idempotencia, aislamiento y controles reales de UI. |
| 02 · Agentes | Idea, guion y storyboard MOCK versionados | JSON válido, límites por rol y errores visibles; decidir backend durable con pruebas de reinicio. |
| 03 · Media | Cinco planos sintéticos y montaje | MP4 vertical inspeccionado con ffprobe y manifest con procedencia. |
| 04 · Estudio | Presets, personajes, QC y revisión | Regeneración selectiva, reconexión y aprobación ligada al hash. |
| 05 · Social | Calendario y dry-run local | Cero envíos, bloqueo de MOCK y reconciliación probada. |
| 06 · HOME | Un proveedor local por etapa | Autorización independiente de descargas, licencias, hardware y benchmark real antes de activar modelos. |
| 07 · Aceptación | Operación, backup, restauración y traslado | Auditar docs/ACCEPTANCE.md con evidencias y revisión humana. |

Antes de cada fase revisar decisiones, documentar bloqueos y probar el flujo anterior. La publicación real requiere autorización separada.
