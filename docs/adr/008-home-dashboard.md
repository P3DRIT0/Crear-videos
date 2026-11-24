# ADR 008 · HOME integrado y recuperación de inferencia

## Inspección y alcance

2026-11-24. El usuario autoriza continuar por integración real en la interfaz y
worker GPU recuperable. Se conserva el árbol de trabajo de la instalación HOME,
sin commits ni push. Se han releído arquitectura, producción, hardware, aceptación,
contratos, cola, renderer, interfaz y código local de ComfyUI 0.46.0.

ComfyUI instalado acepta `prompt_id` UUID del cliente en `/prompt`, pero no se
asume que reenviar ese ID sea idempotente. Su cola e historial permiten reconciliar
un trabajo conservando ID y grafo. Ollama devuelve guiones por petición HTTP local.
Pesos y workflows ya están instalados y medidos. No hacen falta descargas nuevas.

## Decisión y plan

1. Añadir proveedor HOME opt-in al servidor y al contrato, manteniendo MOCK como
   valor predeterminado de clientes antiguos y WORK sin inferencia.
2. Guardar checkpoints de guion, referencia SDXL y cinco clips Wan en el documento
   transaccional de producción existente. Registrar intención y UUID antes del
   envío; recuperar por cola/historial. Si no se puede establecer qué ocurrió,
   detener con diagnóstico de resultado incierto, sin reenvío automático.
3. Compartir exclusión GPU con las herramientas HOME; separar transacciones SQL de
   E/S y liberar modelos. Cancelación por ID, plazos persistentes, intentos limitados,
   hashes, licencias, correlación y recursos observados por etapa.
4. Integrar candidatos y montaje real en el almacén de blobs y rutas ya aisladas
   por marca. Conservar procedencia real y bloquear mezclas con material MOCK.
5. Exponer proveedor, referencia, progreso y fallos en el dashboard. Mantener
   edición, selección, regeneración selectiva y revisión ligada al hash.
6. Probar transporte y fallos con fixtures explícitos, y efectuar un recorrido
   real en HOME, interrumpiendo el servidor mientras ComfyUI sigue trabajando.

El orquestador de esta vertical slice continúa siendo SQL y candado del sistema,
con checkpoints persistentes. No se presenta como Temporal ni como garantía de
exactamente una ejecución en un servicio externo. La migración a Temporal y del
stack HTTP/UI sigue separada; no se añaden servicios a los 16 GB en esta fase.

## Aceptación

- Crear producción HOME desde el navegador y obtener guion Ollama, referencia SDXL,
  cinco candidatos Wan y montaje H.264/AAC/subtítulos con manifest no simulado.
- Reiniciar el worker durante un clip, recuperar el mismo ID y no duplicar su salida.
- Cancelar, reanudar y regenerar un plano sin perder los candidatos de otros planos.
- Errores de proveedor/licencia/timeout visibles, sin fallback remoto o MOCK.
- Persistencia, aislamiento multimarca, revisión y copia/restauración preservados.
- Regresión Python/navegador, OpenAPI y checks; documentar pruebas no ejecutadas.
- No aprobar ni publicar el piloto en nombre del usuario.
