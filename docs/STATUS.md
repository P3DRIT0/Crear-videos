# Estado del proyecto · 24 de noviembre de 2026

## Auditoría y mejoras · estado más reciente

La [auditoría](AUDIT-2026-11-24.md) y el [ADR 009](adr/009-auditoria-local.md)
documentan el endurecimiento posterior a la integración HOME. Se corrigieron
persistencia ante fallos, cleanup/VRAM, rutas/licencias, pérdida de historial,
egreso, estado del lanzador y cargas/SSE del panel. **33 pruebas aprobadas en
38,40 s**, Ruff F, compilación/sintaxis y diff correctos. Navegadores WORK y HOME
aprobados. Ambos entornos pasan comprobación de compatibilidad de dependencias.

Qwen, SDXL y Wan completaron smoke real con los controles de aplicación activos;
petición de descarga denegada sin cambiar modelos. Recuperación sobre copia
restaurada: checkpoint reconstruido y clip auténtico con el mismo SHA-256,
historial perdido, cero nuevos envíos. Backup/restauración de 21 blobs verificados.
Cuatro servicios locales: proxy de denegación, Ollama, ComfyUI y Studio.
Producción bloquea el modo explícito de instalación `--allow-downloads`.

Siguen pendientes la revisión visual humana del piloto, desconexión física,
corte completo del PC, Exyo real y migración al stack objetivo. No se repitió un
reel de cinco planos en esta auditoría ni se hizo auditoría completa de CVEs.
Sin nuevos pesos, drivers, cuentas, publicación, commits ni push. Los apartados
siguientes conservan la evidencia histórica de las fases anteriores; sus
limitaciones quedan ampliadas por el informe actual.

## Integración HOME · dashboard y worker recuperable

**La generación real ya funciona desde el dashboard.** En Nueva producción se
elige HOME para Ollama → referencia SDXL → cinco clips Wan → montaje/QC. MOCK
continúa disponible y WORK bloquea inferencia. El [ADR 008](adr/008-home-dashboard.md)
explica checkpoints, límites y semántica de recuperación; [HOME](HOME.md) describe
la operación. Esta fase no migra a Next.js/FastAPI/Temporal ni activa publicación.

| Aceptación de integración | Resultado observado |
|---|---|
| Creación desde navegador | Campaña y producción HOME creadas en Chromium; Renderizar reel inicia la cadena real. Producción `add9f514-9e1f-4a68-b5e4-c537bd124318`, marca Retrobay |
| Guion y referencia | Ollama produjo JSON validado; SDXL generó la referencia real conservada para todos los clips. El guion preparatorio lleva etiqueta MOCK hasta sustituirse por Ollama |
| Reinicio durante inferencia | Se detuvo y arrancó el estudio con el primer clip en ComfyUI. ID `ed0869d1-c5de-4f3d-9d23-e1d1584399ce` recuperado; un solo envío registrado y una sola salida MP4 con ese prefijo. Guion y referencia conservados |
| Cancelación real | Se canceló el ID `790178d7-ae5a-46d4-89b8-0903f0365964` mediante `/api/jobs/{id}/cancel` del ComfyUI 0.46.0 inspeccionado. Se conservaron los candidatos ya guardados y la reanudación completó el montaje |
| Regeneración selectiva real | Se regeneró el tercer plano. Cambió únicamente su candidato seleccionado; los otros cuatro hashes se conservaron. Hay dos candidatos del tercer plano y se mantiene el montaje anterior |
| Montaje vigente | 15 s, H.264 1080 × 1920 a 24 fps, AAC, mov_text, portada, copy, timeline y manifest. Clips nativos 480 × 832; escalado/recorte en exportación. QC aprobado: cero intervalos negros, pico −19,7 dB |
| Hash del vídeo | `b9da7f32b738b74edd1fd90cc278515c9bb4813262417dd60a1e4ac68703b906` |
| Hash del manifest | `aed984798dd0a29185ac0bff9c384f522e21c5341fdbd01e48978c398459a44b`; contiene modelos, licencias, grafos, IDs, seeds, recursos observados y ejecuciones HOME |
| Navegador HOME | `node scripts/home-browser-verify.mjs`: reproduce el MP4, descarga y verifica el hash del manifest, comprueba cinco licencias descargables, cero errores JS y cero peticiones externas de la página |
| Regresión WORK en navegador | `node tests/dashboard.mjs`: CRUD, montaje MOCK, revisión de fixture, dry-run, móvil y cero solicitudes externas. El harness fija WORK sin HOME para no activar modelos |
| Python | `estudio.cmd test`: **21 pruebas aprobadas en 43,47 s**. Las cinco nuevas usan proveedores loopback explícitamente SIMULADOS y datos temporales: recuperación, envío incierto sin duplicación, cancelación, regeneración, licencias/hashes, OOM visible, aislamiento WORK, backup y exportación Windows |
| Transporte truncado | Se añadió comprobación de Content-Length y error HTTP incompleto; `pytest -q tests/test_providers.py`: dos pruebas aprobadas tras el ajuste |
| Copia/restauración real | 21 blobs referenciados, incluidos candidatos, montajes y textos de licencia. Restauración con el mismo vídeo y cinco licencias verificadas por hash. No incluye pesos ni entornos |
| Exportación | `E:\AI-Creative-Studio\exports\dashboard-retrobay-20261124`: reel-HOME, portada, cinco clips, referencia, subtítulos, copy, timeline, storyboard, manifest y licencias |
| Checks | Compilación Python, sintaxis JS, Ruff sobre archivos nuevos y reglas F sobre todo el código; diff sin errores de espacio |

[Abrir el montaje integrado](http://127.0.0.1:8765/studio?brand=720c761b-64d9-4d3c-9dd5-b1dc2e82edeb&production=add9f514-9e1f-4a68-b5e4-c537bd124318#edit).
Las pruebas y snapshots están en `E:\AI-Creative-Studio\logs`, especialmente
`home-before-restart.json`, `home-recovered.json`, `home-cancelled.json`,
`home-recovery-final.json`, `home-browser-verified.json` y `home-backup-verified.json`.
La copia está en `backups/dashboard-home-20261124` y la restauración en
`backups/dashboard-home-restored-20261124`, relativas a esa raíz.

Durante el desarrollo del harness real se corrigieron esperas de carga del
selector y observación asíncrona del ID en la URL. Se conservaron campañas técnicas
y un borrador preliminar; no se borraron datos. El piloto real identificado arriba
sí completó el recorrido. La última versión del harness de creación no se repitió
desde cero para generar otro piloto; la verificación final independiente y el
recorrido WORK sí terminaron correctamente.

Límites: la recuperación probada mantiene ComfyUI activo mientras reinicia el
estudio. Si desaparece un ID de cola/historial, se muestra resultado incierto y
se requiere reintento explícito; no se promete exactamente una ejecución tras
cualquier fallo de ComfyUI o del PC. El guion puro puede repetirse tras interrupción,
con límite de intentos. Recursos muestreados del dispositivo/sistema, no picos
absolutos ni medidas exclusivas del modelo. No se han probado 720p, 14B, GPU con
otros programas compitiendo ni desconexión física de red. Temporal, LangGraph,
Next.js/FastAPI, PostgreSQL integral y Vitest siguen pendientes del stack objetivo.
El piloto no tiene revisiones ni publicaciones: falta evaluación visual humana.

## Instalación HOME · estado previo a la integración

La instalación doméstica está preparada en `E:\AI-Creative-Studio` con Python,
FFmpeg/ffprobe, Ollama portable, ComfyUI y pesos verificados. RTX 4070 SUPER
de 12282 MiB y RAM física de 15,9 GiB comprobadas. La [guía HOME](HOME.md)
documenta versiones, licencias, arranque y límites. El [ADR 007](adr/007-home-windows.md)
registra las decisiones. No se modificaron drivers, cuentas ni servicios del sistema.

**En esta entrega previa, la inferencia real funcionaba mediante CLI independiente
y el dashboard conservaba su render MOCK.** No se había completado la migración a Next.js/FastAPI/Temporal ni
se ha conectado un worker GPU durable al dashboard. La publicación real sigue
desactivada y ningún piloto ha recibido aprobación visual humana.

| Comprobación HOME | Evidencia real |
|---|---|
| Arranque y reinicio completo | `estudio.cmd stop/start/status`: los tres servicios se detuvieron y volvieron a responder en 127.0.0.1:8765, :11434 y :8188. SQLite esquema 4, storage ok; Retrobay y Exyo persistentes |
| Regresión Python | `estudio.cmd test`: 16 pruebas pytest, incluidos recuperación, cancelación, aislamiento, hash/licencia, montaje, calendario, backup/restore y validación del manifest Ollama 0.40. Última ejecución tras reinicio: 16 aprobadas en 9,13 s |
| Navegador | Chrome 158.0.8127.37 con Playwright Core 1.65.1: CRUD, montaje, revisión de fixture, dry-run y móvil; cero peticiones externas del dashboard. Una ejecución simultánea al piloto GPU agotó el timeout; repetida con GPU libre, pasó en 9,4 s |
| Checks | Compilación Python y sintaxis de ambos JS correctas; Ruff completo en archivos nuevos y reglas F en todo el código correctos; `git diff --check` correcto |
| Ollama real | Qwen3 4B Q4_K_M, digest `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`. El primer guion se rechazó por longitud. Tras concretar las instrucciones: JSON validado en 4,110 s; máximo muestreado 4578 MiB VRAM y 12624 MiB RAM |
| SDXL real | PNG 576 × 1024, 790306 bytes, SHA-256 `91fef3f0158e4e9002dddf98d9dfc5958e1b8c2b65ee21dc177ff12ca31b1954`. 13,406 s; máximos muestreados 8364 MiB VRAM y 12060 MiB RAM |
| Wan real inicial | MP4 288 × 512, 73 frames a 24 fps, 3,041667 s, 311031 bytes. 41,500 s; máximos muestreados 11611 MiB VRAM y 13897 MiB RAM. Presenta artefactos visibles; no aprobado visualmente |
| Primer piloto de cinco planos | `reels/retrobay-20261124-163729/reel.mp4`: cinco planos I2V de 3 s con referencia común; H.264 1080 × 1920 escalado desde 288 × 512, 24 fps, AAC y mov_text. QC técnico aprobado, 15,000 s, pico −19,7 dB, cero intervalos negros. SHA-256 `c3489f9894a4eeb3f269a9f636333fb64d01ab60e0c5acaa12b2d3d721ecde6d`. Calidad visual pendiente |
| Prueba 480 × 832 | Carga FP8 del mismo peso FP16; clip I2V de 3,041667 s generado sin OOM. 85,328 s hasta el fallo de postproceso del comando manual por omitir PATH de ffprobe. El mismo archivo se validó con ffprobe después, sin regenerarlo ni alterar el informe fallido. `benchmarks/clip480-20261124-164321/validation.json`; muestras de 11607 MiB VRAM y 11815 MiB RAM |
| **Piloto HOME vigente · 480 × 832** | `reels/retrobay-20261124-164623/reel.mp4`: cinco planos I2V reales, semillas y referencia común verificadas. Exportación escalada H.264 1080 × 1920, 24 fps, AAC y mov_text; 15,000 s, 9051787 bytes. QC técnico aprobado: cero intervalos negros, pico −19,7 dB. SHA-256 `4d25a880743232f94e8e6e959955898d509da68948203ce8678b216d7a78abf6`. Etapas de inferencia y probe: 432,814 s acumulados, excluyendo verificación previa de pesos y montaje. Máximos muestreados: 11422 MiB VRAM, 11030 MiB RAM. Revisión humana pendiente |
| Backup real de configuración | Copia y restauración en `backups/home-setup-20261124` y `home-restore-20261124`: dos marcas recuperadas. Cero blobs en esta base nueva; los medios HOME CLI están fuera de SQLite y deben copiarse aparte |
| Licencias e inventario | Cinco pesos con fuentes, versiones, tamaños, SHA-256 y licencias en `licenses/verified-assets.json`; código y paquetes en `installation.json`. Archivos pesados fuera del repositorio |
| Traslado HOME | `scripts/package.py` actualizado para incluir catálogo JSON, lanzador CMD y ambos locks HOME. Paquete final de fuentes: `exports/creative-studio-home-final-20261124.zip`, 86 archivos con inventario SHA-256; excluye datos, pesos, entornos y credenciales |
| Red observada | Servicios en loopback, Ollama sin nube, ComfyUI offline sin custom nodes, HF offline. Muestra de conexiones externas de esos procesos: ninguna. Sin prueba de desconexión física ni aislamiento de firewall |

Las rutas de artefactos de la tabla son relativas a `E:\AI-Creative-Studio`.
Los valores de recursos son máximos muestreados de todo el dispositivo/sistema
cada segundo. No son benchmarks universales. El guion válido pertenece al segundo
intento, con cargas previas; no se presenta como tiempo de arranque en frío.
La configuración CLI se ajusta a 480 × 832 con carga FP8 después de la prueba.
El piloto vigente se generó entero con el lanzador y completó sus cinco informes
de benchmark, montaje, QC y portada. El primer piloto de 288 × 512 se conserva
como diagnóstico y no es la entrega visual recomendada para revisar.

No ejecutados en HOME: migraciones sobre PostgreSQL real (no hay Docker),
Temporal, LangGraph, build Next.js, Vitest ni API FastAPI (no forman parte del
ejecutable existente). Sin prueba física offline, evaluación humana de calidad,
publicación real, voz neural o música generada por modelo. El histórico siguiente
describe WORK y no sustituye estas limitaciones actuales.

## Histórico WORK

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
