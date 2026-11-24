# Estado del proyecto · 24 de noviembre de 2026

**La cadena WORK está operativa de campaña a reel MOCK y dry-run.** El dashboard y el worker usan CPU y SQLite. Las fichas y campañas de 01 se conservaron al migrar. El piloto Retrobay tiene un montaje descargable. Su revisión editorial queda en manos del usuario.

## Aceptación actual

| Fase | Resultado | Evidencia |
|---|---|---|
| 02 · Agentes | Productor, guionista, storyboard y decisiones editoriales locales, con contratos Pydantic, roles, presupuestos, versiones y hashes. Edición de la idea con historial. | Validación de determinismo, tiempo, entradas, aislamiento y recorrido en Chromium. Proveedor MOCK visible. |
| 03 · Media | Cinco planos, geometría y sonido originales, clips por hash, timeline editable, montaje H.264/AAC, SRT, portada, copy y manifest. | FFmpeg real; ffprobe sobre el MP4 exportado. QC de dimensiones, fps, duración, audio, subtítulos, clipping e intervalos negros. |
| 04 · Estudio | Personajes y referencias versionadas, siete presets, comparación de candidatos, regeneración selectiva, política de revisión, catálogo de licencias/candidatos, actividad SSE y reanudación por ID. | Worker interrumpido durante un job, reanudación sobre checkpoints, cancelación en curso y verificación del hash tras cambiar de candidato. |
| 05 · Social | Calendario dry-run por marca, umbral de revisión, límite diario, ventana de Madrid, pausa y conciliación idempotente en SQL. Conteos locales y ejemplos analíticos etiquetados. | Browser y API completan una simulación con revisión de fixture. El piloto del usuario conserva cero aprobaciones y cero publicaciones. |
| 06 · HOME | Inventario portátil, adaptadores loopback y runner de benchmarks para guion, imagen y clip; control exclusivo de GPU, verificación local de hashes/licencias y reporte de recursos muestreados. | Contratos probados con servidores fixture. Hardware presente en WORK: GT 1030. Faltan RTX, RAM doméstica confirmada, pesos autorizados y smoke tests reales en HOME. |
| 07 · Aceptación | Pruebas locales, exportación, copia coherente de SQLite/blobs, restauración con integridad y paquete de traslado. | Comandos y resultados en esta página; operación reproducible en la guía. |

### Reel del piloto

**Retrobay · El último píxel** utiliza el personaje Lumen. Los cinco planos duran cuatro segundos cada uno. La geometría base es de 135 × 240 y la salida se escala a 1080 × 1920. La rúbrica humana de identidad, continuidad y narrativa sigue pendiente. Las escenas, las decisiones editoriales y el vídeo del piloto están identificados como MOCK.

- Producción `1dfb9408-a2ee-42c8-92ca-0fcc22fd83f4` de la campaña `f38a529b-6a2d-4508-9c8a-a21706b9f007`.
- [Abrir montaje en el estudio local](http://127.0.0.1:8765/studio?brand=720c761b-64d9-4d3c-9dd5-b1dc2e82edeb&production=1dfb9408-a2ee-42c8-92ca-0fcc22fd83f4#edit).
- Exportación local en `.studio/exports/entrega-retrobay/`. El manifest contiene la procedencia, las decisiones, el timeline, los hashes y el QC. Los archivos de ejecución viajan separados del código.

### Pruebas y artefactos actuales

| Comando o recorrido | Resultado observado en WORK |
|---|---|
| `./scripts/setup` y `./scripts/dev` | SQLite, esquema 4, almacenamiento operativo, servicio en loopback 8765. |
| `./scripts/check` | Compilación Python, sintaxis JS, 15 pruebas unittest aprobadas, recorrido Chromium con 0 solicitudes externas, cuatro migraciones SQL up/down/up sobre PostgreSQL 17.9 sin red. |
| `./scripts/export` sobre el piloto | Seis productos del montaje, storyboard JSON y cinco MP4 individuales. El tercer plano tiene un candidato alternativo. Cambió únicamente su hash al regenerarlo. |
| `ffprobe` sobre la exportación final | H.264 1080 × 1920 a 24/1, AAC, mov_text, 20,000 s, 3.616.759 bytes. Pico −19,4 dB y cero intervalos negros detectados con los umbrales del renderer. Chromium reprodujo el MP4 final desde el servidor. |
| `./scripts/data backup` y `./scripts/data restore` | 31 blobs verificados. El servidor arrancado sobre la copia restaurada recuperó la ficha original, los cinco clips y el reel final con los mismos hashes. |
| Inventario y secretos | `python3 scripts/home-inspect.py` ejecutado en WORK. Búsqueda local de cabeceras de claves privadas y patrones comunes de tokens sin coincidencias en fuentes. |
| Paquete de traslado | `python3 scripts/package.py .studio/exports/creative-studio-work.zip` crea ZIP de código con inventario SHA-256. El ZIP excluye la base, los medios, credenciales, dependencias instaladas y pesos. |

SHA-256 del reel final: `d04e36d9430390b74c54157494aa9449175660d6b83b1e55ac97e04329f88332`. La copia de datos está en `.studio/backups/entrega-final` y la restauración comprobada en `.studio/backups/entrega-restaurada`. Se conserva además el backup previo a la ampliación.

### Archivos entregados en esta ampliación

| Ubicación | Contenido |
|---|---|
| apps/api/agents.py, editorial.py, production.py y worker.py | Roles, decisiones, producción, eventos, revisión y cola CPU |
| apps/api/media.py, backup.py y export.py | Material original, codificación/QC, copias y exportación |
| apps/api/db.py, server.py y service.py | Migraciones incrementales, API versionada, streaming de eventos, descargas y compatibilidad con campañas/fichas |
| packages/contracts/production.py, routes.py y packages/local_lock.py | Contratos/OpenAPI y exclusión entre procesos |
| infra/migrations/002_production.*, 003_models.* y 004_policy.* | Producciones, personajes, eventos, calendario, registros de modelos y políticas por marca |
| apps/dashboard/studio.html, studio.js, style.css, index.html y app.js | Dashboard de producción integrado con las campañas |
| integrations/local.py y home.py | Clientes de proveedores y benchmark HOME independiente |
| scripts/check, data, export, worker, package.py, home-inspect.py y test-postgres | Verificación, operación y traslado |
| tests/test_production.py, test_providers.py, test_core.py, studio-flow.mjs y dashboard.mjs | Pruebas HTTP, workers, fixtures de proveedores y recorrido del operador |
| [ADR 005](adr/005-produccion-work.md), [ADR 006](adr/006-upstream.md), [operación](OPERACION.md) y [README](../README.md) | Decisiones, auditoría de fuentes oficiales, pasos de operación y bloqueos |

### Límites de la entrega

La orquestación probada utiliza SQL y candado local. Temporal, LangGraph, FastAPI, Next.js y el driver psycopg siguen pendientes del entorno objetivo. El navegador utiliza la API local existente. PostgreSQL tiene pruebas de migraciones sobre el motor real; el flujo de producción íntegro se probó con SQLite. WORK nunca activa inferencia. Los fixtures de ComfyUI/Ollama prueban el contrato de transporte; no acreditan rendimiento o compatibilidad de pesos. Los adaptadores reales de publicación quedan fuera del ejecutable. El análisis visual humano se registra desde el dashboard. No se llamó a Meta ni a Postiz.

## Histórico · entrega inicial de fase 01

La evidencia siguiente corresponde a la versión con esquema 1. El estado vigente es el de la tabla de aceptación superior.

## Punto de partida y recursos

El directorio inicial estaba vacío, sin historial Git. Se incorporó a la raíz el contenido de `creative-studio-context.zip`. Se leyeron AGENTS, todos los documentos de docs, el perfil propuesto y los prompts para delimitar 01. No se inicializó un repositorio Git ni se usaron cuentas externas.

| Recurso de WORK | Observación local |
|---|---|
| SO / CPU | CachyOS Linux x86_64, Intel Core i7-4790, 8 CPU lógicas |
| Memoria y disco | MemTotal 16.247.160 KiB; 196 GiB libres en el volumen de trabajo al inspeccionarlo |
| GPU detectada | GeForce GT 1030, 2048 MiB. Ninguna tarea GPU ejecutada |
| Runtime | Python 3.14.10, SQLite 3.54.1, Pydantic 2.14.2, Node 22.23.5, npm 10.9.9 |
| Infraestructura local | Docker rootless 29.10.0, Compose 5.8.0, imagen PostgreSQL 17.9 disponible por digest |
| Otras herramientas | FFmpeg n9.1 y ffprobe en PATH; Playwright Core 1.60.0 y Chromium headless 148.0.7778.96 usados para el test UI |
| Equipo HOME | RTX 4070 Super de 12 GB según el encargo. RAM de 16/32 GB por confirmar en casa; rendimiento sin medir |

## Cambios entregados

| Archivos | Resultado |
|---|---|
| [ADR 001](adr/001-dependencias.md), [002](adr/002-limites.md), [003](adr/003-contratos.md), [004](adr/004-fases.md) | Decisiones sobre dependencias, licencias del runtime, límites, contratos, secuencia y aceptación |
| [README](../README.md), [.env.example](../.env.example), [.gitignore](../.gitignore), [requirements-work.lock](../requirements-work.lock) | Arranque local, valores de configuración, exclusiones y versiones observadas |
| apps/api/{config,db,executor,server,service,storage}.py | Perfil WORK, API v1, transacciones, operación síncrona de ficha y almacén por hash |
| packages/contracts/{models,routes}.py | Modelos Pydantic, validación de entradas y contrato OpenAPI 3.1 servido por la API |
| infra/migrations/001_core.{up,down}.sql | Historial de versión, semilla, aislamiento referencial y reversión del esquema |
| apps/dashboard/{index.html,style.css,app.js} | Resumen, Campañas, Jobs y Sistema; controles sobre la API y estados de error |
| scripts/{setup,dev,test,test-ui,test-postgres} | Comprobación, arranque y tres pruebas independientes |
| tests/{test_core.py,dashboard.mjs} | Pruebas de núcleo por HTTP y recorrido en navegador |
| docs/STATUS.md | Inventario, evidencia y pendientes de esta entrega |

Los restantes ficheros del ZIP conservan su contenido de referencia. Los datos de ejecución se excluyen con .gitignore.

## Comprobaciones ejecutadas

Desde la raíz en este WORK:

| Comando | Resultado observado |
|---|---|
| `./scripts/setup` | Salida 0, backend sqlite, esquema 1, almacenamiento ok |
| `./scripts/dev` | Escuchó en 127.0.0.1:8765. Peticiones HTTP reales a /, CSS, JS, brands, health y openapi.json devolvieron 200. Proceso detenido con Ctrl+C después del smoke |
| `curl --noproxy '*' -fsS http://127.0.0.1:8765/api/v1/health` | Con el servidor en marcha devolvió `{"database":"sqlite","schema_version":1,"status":"ok","storage":"ok"}` |
| `./scripts/test` | 8 pruebas unittest aprobadas. Cubren CRUD, hash, reinicio, mutaciones concurrentes e idempotentes, reutilización de blobs, aislamiento de marcas, límites de entradas/origen/rutas, fallo de disco, reintento, integridad y migración reversible |
| `./scripts/test-ui` | Chromium realizó CRUD y descarga, verificó el hash y el conflicto de borrado, navegó en móvil y comprobó ausencia de solicitudes externas de la página y errores JS |
| `./scripts/test-postgres` | PostgreSQL 17.9 real en contenedor efímero sin red. DDL up/down/up, Retrobay, referencia de marca, bloqueo de borrado y requisito de hash correctos |
| `python3 -m compileall -q apps packages tests` y `node --check apps/dashboard/app.js` | Ambos terminaron con salida 0 |
| `STUDIO_DB=postgres ./scripts/setup` | Salida 1 esperada con mensaje que identifica psycopg 3 ausente y la alternativa SQLite |

Los errores OSError que aparecen en la suite corresponden a fallos inyectados para verificar respuestas 503 y la recuperación. Las pruebas no miden rendimiento audiovisual ni la capacidad de HOME.

## Bloqueado o pendiente

- **PostgreSQL de extremo a extremo.** SQL verificado sobre el motor real. Falta psycopg 3 en el intérprete WORK para verificar API → socket Unix → PostgreSQL. El modo SQLite cubre el flujo completo.
- **Stack objetivo.** FastAPI, Uvicorn, SQLAlchemy, Alembic y Next.js no estaban disponibles en el entorno de proyecto. Se usan el servidor HTTP de desarrollo de Python, Pydantic, migraciones SQL y un dashboard estático del mismo origen. El arranque prescinde de un build frontend. Ruff, pytest, Vitest y el build de Next quedan sin ejecutar. Los checks disponibles figuran arriba.
- **Durabilidad del orquestador.** La fase 01 tiene un ejecutor manual síncrono. Conserva las fichas confirmadas y admite repetición manual tras fallo. Temporal y los workers con recuperación automática son trabajo posterior.
- **Aceptación audiovisual.** Guion, storyboard, MP4, revisión, calendario, servicios de inferencia y publicación corresponden a fases posteriores. No se instalaron paquetes, drivers o modelos. No hubo conexión a proveedores, cuentas ni publicación.

## Validación de campaña en WORK

Se creó **Retrobay · El último píxel** desde Chromium en el dashboard con un objetivo editorial propuesto para el piloto. Un cursor sigue un píxel de luz hasta revelar el nombre Retrobay. El objetivo fija cinco planos y un bucle de 20 segundos para un futuro reel.

La campaña y su job quedaron guardados en el directorio persistente `.studio`. Desde la pantalla Jobs se ejecutó la ficha y se descargó el JSON de 527 bytes. El SHA-256 de la descarga coincidió con el mostrado en pantalla. Tras detener y volver a iniciar el servidor con `./scripts/dev`, la API devolvió el mismo job completado y los mismos bytes que el almacén local.

| Registro | Valor verificado |
|---|---|
| Campaña | `f38a529b-6a2d-4508-9c8a-a21706b9f007` |
| Job | `361b023a-b405-4eaa-9fc3-b993412bc763` |
| SHA-256 | `2c0e872a288d954685c726bf6d8b0cba85bb219e85ee152f151aabd0f9d52ae8` |

En ese punto la suite de núcleo volvió a pasar sus ocho pruebas. La ampliación posterior conserva la ficha y se documenta al inicio de esta página.
