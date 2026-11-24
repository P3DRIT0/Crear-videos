# ADR 009 · Auditoría y endurecimiento local

## Alcance y autorización

2026-11-24. El usuario solicita auditoría y corrección de lo mejorable. Se conserva
el árbol de trabajo, los datos y pilotos existentes, sin commits, push, publicación,
drivers, nuevos pesos ni servicios externos. Se releen AGENTS, arquitectura,
producción, hardware, aceptación, STATUS y prompt 07 antes de implementar.

## Hallazgos iniciales y plan

1. No sobrescribir etapas completadas cuando falla el preflight de la siguiente.
2. Guardar resultados antes del cleanup de VRAM y evitar liberar memoria de otro
   trabajo. Descargar ComfyUI antes de cargar Ollama.
3. Fijar rutas y textos de licencia de los pesos, no solo el digest declarado;
   rechazar registros duplicados o rutas de carga distintas de las auditadas.
4. Recuperar resultados terminados con evidencia local y metadata de workflow
   si se pierde el historial ComfyUI; mantener parada segura si no hay prueba.
5. Reforzar offline en procesos propios sin modificar firewall ni políticas del
   sistema. Python solo conectará a loopback; HTTP externo de Ollama se dirigirá
   a un proxy local que deniega peticiones. Verificar sin descargar pesos.
6. Hacer atómico el estado del lanzador y serializar start/stop. Corregir cargas
   asíncronas de la interfaz y reconexión SSE por cursor.
7. Ejecutar regresión, fallos inyectados explícitamente SIMULADOS, checks, navegador
   y smoke real acotado; revisar respaldo/restauración y documentar evidencias.

## Aceptación

- Regresión WORK/HOME y aislamiento conservados.
- Cada hallazgo corregido tiene evidencia o prueba específica, sin inventar métricas.
- Recuperación sin nuevo POST ante un resultado local auténtico; archivos ajenos,
  ambiguos, corruptos o con grafo diferente no se reutilizan.
- Bloqueo de conexión externa probado; inferencia local comprobada con los modelos
  existentes. Distinguir controles de aplicación de aislamiento del SO.
- Informe en docs/AUDIT-2026-11-24.md, README y STATUS actualizados.

No se mezcla esta auditoría con una reescritura a Next.js/FastAPI/Temporal. Esa
migración conserva su lugar en el plan objetivo. La aceptación visual humana y
la publicación requieren actuaciones independientes del operador.
