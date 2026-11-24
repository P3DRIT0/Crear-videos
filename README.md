# AI Creative Studio

Estudio audiovisual multimarca local. El dashboard permite elegir entre previsualización MOCK con CPU e inferencia HOME con Ollama, SDXL y Wan 2.2. HOME genera un guion, una referencia y cinco clips, conserva candidatos por hash y monta un reel con audio y subtítulos. La cola guarda checkpoints SQL y recupera los IDs de ComfyUI tras reiniciar el worker. La revisión y el calendario dry-run funcionan en local.

## Arranque en este equipo de casa · Windows

Ejecutar **`estudio.cmd`** con doble clic, o `./estudio.cmd start` desde PowerShell.
Abrir **http://127.0.0.1:8765/studio**. `./estudio.cmd status` comprueba los cuatro
servicios y `./estudio.cmd stop` los detiene. No requiere cambiar la política de
ejecución de PowerShell ni instalar servicios del sistema.

La instalación y los datos HOME residen en `E:\AI-Creative-Studio`, para no llenar
C:. RTX 4070 SUPER de 12 GB y RAM de 16 GB comprobadas. Retrobay y Exyo están
creadas en la base HOME. La [guía HOME](docs/HOME.md) explica las pruebas reales,
licencias, comandos de benchmark, piloto y reinstalación. Las versiones Python
están fijadas en `requirements-home.lock` y `requirements-comfy-home.lock`.

La [auditoría del 24-11-2026](docs/AUDIT-2026-11-24.md) documenta correcciones de
recuperación, memoria, licencias, red y panel, con 33 pruebas aprobadas y smoke
real de los tres proveedores. El cuarto servicio es un proxy local que deniega
egreso; el lanzador no permite descargas durante producción. Siguen pendientes
la aceptación visual humana y la prueba con red físicamente desconectada.

Para generar desde la interfaz: **Nueva producción → Proveedor HOME → Renderizar
reel**. HOME usa el perfil medido de cinco planos de tres segundos, con referencia
común y clips nativos de 480 × 832, escalados y recortados a 1080 × 1920 al montar.
El selector MOCK conserva la previsualización procedural. Un fallo HOME se muestra
como error; no se sustituye por MOCK ni por un proveedor remoto.

**Cancelar render** conserva los planos guardados; **Reintentar / reanudar** utiliza
checkpoints e historial del proveedor. **Regenerar** afecta solo al plano elegido.
En Montaje se reproducen y descargan reel, portada, subtítulos, copy, timeline y
manifest. Biblioteca permite descargar las licencias utilizadas. Cada cambio del
montaje invalida su revisión anterior. La publicación real permanece desactivada.

El [piloto HOME integrado](http://127.0.0.1:8765/studio?brand=720c761b-64d9-4d3c-9dd5-b1dc2e82edeb&production=add9f514-9e1f-4a68-b5e4-c537bd124318#edit)
pasó QC técnico y sigue pendiente de revisión visual humana. Las herramientas CLI
`./estudio.cmd benchmark --stage script`, `--stage image`, `--stage clip` y
`./estudio.cmd reel` se conservan como herramientas independientes de diagnóstico.

## Producir un reel

Después del arranque, entra en **Producción**, selecciona la marca y abre **Nueva producción**. Elige la campaña, la idea, el preset y el personaje. Revisa los planos y pulsa **Renderizar reel**. En **Montaje** puedes reproducir el resultado, cambiar el orden y descargar vídeo, portada, subtítulos, copy, timeline y manifest. En **Revisión** se puntúa el hash actual. La programación y la analítica simulada están en **Calendario**.

La [guía de operación](docs/OPERACION.md) cubre versiones, recuperación del worker, copia/restauración, exportación y traslado a HOME. El [estado de aceptación](docs/STATUS.md) registra pruebas reales y límites pendientes.

## Arranque verificado en WORK

Desde la raíz del proyecto, en Linux con Python 3.14 y los paquetes locales de `requirements-work.lock`:

```sh
./scripts/setup
./scripts/dev
```

Abrir **http://127.0.0.1:8765/studio** para producir o **http://127.0.0.1:8765** para administrar campañas. Para detener el proceso, pulsar Ctrl+C. El setup comprueba dependencias, aplica la migración inicial de forma transaccional y prueba la escritura en disco. Se puede repetir. El arranque también aplica la migración si hace falta. Ningún script instala paquetes.

Para crear una ficha de campaña desde el resumen:

1. Pulsar **Nueva campaña**, escribir nombre y objetivo y guardar.
2. En la campaña, pulsar **Crear job** y guardar. En **Jobs**, pulsar **Ejecutar**.
3. Abrir **Descargar ficha**. El JSON contiene versión, marca y campaña en el momento de la ejecución. La interfaz muestra el SHA-256 de los bytes descargados.
4. Reiniciar con el mismo directorio de datos para recuperar campañas, jobs y fichas. Es posible editar el objetivo y crear otro job para guardar una nueva ficha. Para eliminar una campaña se deben eliminar antes sus jobs.

### Configuración y datos

El proceso lee variables del entorno al arrancar. Los valores predeterminados coinciden con [.env.example](.env.example). El lanzador Windows configura su entorno explícitamente y no ejecuta `.env`. Para usar una copia local editada en una shell POSIX se puede ejecutar `set -a`, `. ./.env` y `set +a` antes del arranque. Se presupone que el operador controla ese fichero.

| Variable | Predeterminado | Uso |
|---|---|---|
| STUDIO_PROFILE | work | WORK sin inferencia; home16 requiere opt-in y modelos verificados |
| STUDIO_PORT | 8765 | Puerto de loopback |
| STUDIO_DATA | .studio | Directorio privado, relativo a la raíz o absoluto |
| STUDIO_DB | sqlite | Modo reducido verificado; postgres requiere psycopg 3 |
| STUDIO_ENABLE_HOME | 0 | Solo home16 permite activarlo con valor 1 |
| STUDIO_HOME_ROOT | sin valor | Raíz absoluta de instalación de modelos, configurada por estudio.cmd |
| STUDIO_PG_SOCKET | /var/run/postgresql | Directorio absoluto de socket Unix del servidor PostgreSQL opcional |

SQLite reside en `.studio/studio.sqlite3` y los blobs en `.studio/blobs/<sha256>`. Una copia de ese directorio **con el proceso detenido** conserva el estado del modo reducido. Las pruebas crean sus propios datos temporales. El YAML de ejemplo sigue describiendo el diseño de WORK/HOME. Los límites activos de la aplicación se pueden consultar en **Sistema**.

La API se sirve en el mismo origen. El contrato completo está en `/api/v1/openapi.json` y el health check en `/api/v1/health`. El health check abre la base de datos, comprueba la versión del esquema y prueba escritura temporal en el almacén.

## Verificación local

```sh
./scripts/test
./scripts/test-ui
./scripts/test-postgres
```

La suite de núcleo usa el runtime WORK y FFmpeg/ffprobe para la prueba de codificación real. El segundo usa Node y Playwright Core con Chromium ya instalados; acepta `PLAYWRIGHT_CORE` y `CHROMIUM_PATH` para rutas locales. El tercero requiere Docker local y el digest de PostgreSQL ya presente que se identifica en el ADR 001. Prueba las cuatro migraciones SQL dentro de un contenedor aislado. No descarga imágenes ni utiliza una base existente.

El adaptador Python alternativo espera psycopg 3, una base dedicada llamada `creative_studio` y acceso por el socket Unix de PostgreSQL en el puerto 5432. El usuario local debe poder crear las tablas en esa base. En WORK falta el controlador. Utilizar el modo SQLite predeterminado. Las decisiones, los bloqueos y el inventario de pruebas constan en [STATUS](docs/STATUS.md).

## Especificación de partida

El ZIP aportó [AGENTS.md](AGENTS.md), [la arquitectura](docs/ARCHITECTURE.md), los requisitos de producción y hardware, los criterios de aceptación, el ejemplo YAML y los prompts. Las fases 02–05 y la aceptación local de 07 se ejecutan en WORK. HOME añade inferencia integrada y herramientas de diagnóstico. La revisión visual y la migración al stack objetivo siguen pendientes. El [ADR 008](docs/adr/008-home-dashboard.md) delimita la recuperación SQL de esta versión; no es una implementación Temporal.
