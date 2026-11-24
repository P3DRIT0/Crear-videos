# ADR 001 · Dependencias de WORK
Aceptada para la fase 01 el 24-11-2026.

El kit solo aporta especificaciones. WORK ya tiene Python, SQLite, Pydantic 2, Node, un navegador y Docker rootless con una imagen PostgreSQL 17.9 por digest. No hay FastAPI, Uvicorn, SQLAlchemy, Alembic, psycopg, Next.js ni Temporal disponibles en el proyecto. No instalar ni buscar servicios en red.

Servir el dashboard HTML/CSS/JS y la API desde el mismo proceso Python en loopback. Usar Pydantic para los contratos y unittest como runner. SQLite es el arranque reproducible reducido. Compartir el esquema SQL versionado y las operaciones entre SQLite y el adaptador opcional psycopg 3. Validar el esquema en PostgreSQL aislado usando exclusivamente la imagen local y un volumen efímero. No utilizar bases o imágenes de aplicaciones ajenas. La prueba SQL y la prueba de la API con el controlador son verificaciones distintas.

Conservar las rutas y esquemas al adoptar FastAPI, SQLAlchemy/Alembic y Next/TypeScript. Antes de migrar, fijar dependencias compatibles en un entorno aparte, probar el contrato y los datos existentes y solo entonces sustituir el adaptador. No hacen falta Redis, S3, una cola distribuida ni un modelo para producir una ficha JSON. El servidor de desarrollo se limita al puesto monousuario.

## Inventario del runtime Python de terceros

Versiones del entorno que ejecutó las pruebas, fijadas en `requirements-work.lock`. Licencias leídas de los paquetes instalados. La huella identifica el fichero RECORD local que enumera los ficheros de la distribución y sus hashes. Para una instalación futura habrá que verificar los hashes de los wheels específicos de esa plataforma. No se redistribuyen estos paquetes con la aplicación.

| Paquete y origen declarado | Versión | Licencia declarada | SHA-256 del RECORD instalado |
|---|---|---|---|
| [pydantic](https://github.com/pydantic/pydantic) | 2.14.2 | MIT | `26ffc842efe81d736a5a2b31b9cbf05cc64fb2b1aec3c199f9ff027e40e95659` |
| [pydantic-core](https://github.com/pydantic) | 2.50.2 | MIT | `a1d4847d8273e81b699d34fc06a4f0c90f6cf45613ea7f74cd0a7e36febf7424` |
| [annotated-types](https://github.com/annotated-types/annotated-types) | 0.8.0 | MIT | `e2d277fb1ec003e592539acab2b24b52a067ad2f6c9e822e844d449535912f56` |
| [typing-extensions](https://github.com/python/typing_extensions) | 4.16.0 | PSF-2.0 | `b587cb5b7b3a871f48aebb89b0017695773aab83eff436a49eb8c7e68867a55b` |
| [typing-inspection](https://github.com/pydantic/typing-inspection) | 0.4.5 | MIT | `56ce1a8fbdc2c7ad6fea64bfcd7e73e0573260067fa55a1a7b847113eccaf40e` |

MIT permite uso comercial con conservación de los avisos de copyright y licencia en copias o partes sustanciales. Para typing-extensions se conservan los avisos y condiciones de PSF-2.0 al redistribuirlo. La interfaz usa texto, CSS y fuentes del sistema; el JSON solo contiene datos locales. Las licencias de pesos, medios y servicios futuros quedan pendientes de la auditoría del artefacto exacto.

PostgreSQL de prueba procede de la imagen local `postgres@sha256:c7526c0f6c3f30260a563d7bcf8ad778effac59a44f8ffa86678c35418338609`. El script usa `--pull=never`, red desactivada, un contenedor nuevo y datos temporales. Playwright y Chromium son herramientas de prueba preexistentes, ajenas al arranque. Ninguna imagen o herramienta se incorpora al paquete.
