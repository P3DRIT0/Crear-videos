# AI Creative Studio

Estudio audiovisual multimarca para WORK. Convierte una campaña en guion, storyboard y reel de previsualización MOCK. Genera cinco planos con CPU, monta un MP4 vertical con audio y subtítulos y conserva cada versión por SHA-256. La revisión y el calendario dry-run funcionan en local. El piloto de Retrobay se puede abrir en el estudio.

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

El proceso lee variables del entorno al arrancar. Los valores predeterminados coinciden con [.env.example](.env.example). Para usar una copia local editada en una shell POSIX se puede ejecutar `set -a`, `. ./.env` y `set +a` antes del arranque. Se presupone que el operador controla ese fichero.

| Variable | Predeterminado | Uso |
|---|---|---|
| STUDIO_PROFILE | work | Único perfil operativo |
| STUDIO_PORT | 8765 | Puerto de loopback |
| STUDIO_DATA | .studio | Directorio privado, relativo a la raíz o absoluto |
| STUDIO_DB | sqlite | Modo reducido verificado; postgres requiere psycopg 3 |
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

El ZIP aportó [AGENTS.md](AGENTS.md), [la arquitectura](docs/ARCHITECTURE.md), los requisitos de producción y hardware, los criterios de aceptación, el ejemplo YAML y los prompts. Las fases 02–05 y la aceptación local de 07 se ejecutan en WORK; la inferencia real de 06 requiere el equipo HOME. El [plan por fases](docs/adr/004-fases.md) define sus puertas de aceptación. HOME requiere comprobar el equipo real y autorizar las descargas por separado.
