# Operación y traslado

## WORK

En la raíz, ejecutar `./scripts/setup` y `./scripts/dev`. La API, la interfaz y el worker CPU usan el mismo directorio privado. El dashboard se abre en http://127.0.0.1:8765 y el estudio en http://127.0.0.1:8765/studio. La configuración por defecto es SQLite. El ejecutor de fichas de 01 continúa siendo síncrono. La cola de vídeo usa checkpoints en SQL y un candado de proceso en el directorio compartido. El indicador de un job se refiere a CPU; el presupuesto GPU de WORK es cero.

1. En el resumen, crear la campaña. En **Producción → Biblioteca**, guardar el personaje y sus versiones. El estudio genera referencias propias de frente, perfil y espalda.
2. Crear una producción a partir de la idea. El **Storyboard** muestra cinco planos editables. **Versionar idea** conserva el historial y permite cambiar preset o personaje. El indicador MOCK corresponde a previsualización procedural. Los siete presets cambian instrucciones y paleta; la estética del proveedor WORK es pixel art.
3. Usar **Renderizar reel**. El worker confirma cada plano. Se puede cancelar desde la interfaz y reanudar con el mismo botón. Si faltan FFmpeg/ffprobe o los códecs libx264 y AAC, WORK permite preparar la campaña, el guion y el storyboard. Para codificar, trasladar el backup a un equipo local con esas herramientas. Ante un fallo de FFmpeg se conserva el diagnóstico y se reutilizan los planos ya completados. `./scripts/worker` inicia un consumidor separado si se quiere comprobar recuperación. Ambos procesos se excluyen mediante el mismo candado.
4. En **Montaje** se puede cambiar el orden sin destruir los clips. Regenerar o editar un plano conserva los candidatos y los montajes previos. El montaje final incluye H.264, AAC y subtítulos. Las descargas también incluyen SRT, portada PNG, copy, timeline y manifest JSON. La imagen procedural original se escala a 1080 × 1920.
5. Reproducir el vídeo en **Revisión** y registrar observaciones y puntuaciones propias. Una aprobación pertenece a un hash y a un montaje vigente. En **Calendario**, programar una simulación y ejecutarla una vez alcanzada su hora. **Editar política** controla el cupo diario, ventana de Madrid, umbral humano y pausa de la marca. El registro de simulaciones se obtiene de SQLite. Los ejemplos de impresiones/reproducciones están marcados como fixtures.
6. Para verificar el sistema, ejecutar `./scripts/check`. Usa Python, Node, el navegador e imagen PostgreSQL ya existentes. Si solo están disponibles Python, Pydantic, FFmpeg y ffprobe, ejecutar `./scripts/test`. En Windows las entradas Python equivalentes se ejecutan desde la raíz con `python -m apps.api.server` y `python -m unittest discover -s tests -v`; el arranque completo de Windows queda pendiente de prueba en HOME.

## Copia y restauración

```sh
./scripts/data backup ../copia-studio
./scripts/data restore ../restaurado --source ../copia-studio
STUDIO_DATA=../restaurado STUDIO_PORT=8766 ./scripts/dev
```

Cada destino debe ser nuevo. El backup usa la API de snapshot SQLite y copia los blobs inmutables referenciados, incluidos candidatos, referencias y exportaciones históricas. Comprueba integridad SQL, relaciones y SHA-256. La restauración verifica de nuevo la base y los bytes antes de hacer visible el resultado. Los ficheros de exportación legibles se pueden recrear a partir del estado restaurado con `./scripts/export MARCA_UUID PRODUCCION_UUID DIRECTORIO_NUEVO`. Para PostgreSQL haría falta un procedimiento equivalente con pg_dump y snapshot coordinado con los blobs.

## Traslado a HOME

```sh
python3 scripts/package.py ../creative-studio-work.zip
```

El ZIP guarda código, documentación, migraciones, scripts, configuración de ejemplo y hashes. Los datos del piloto viajan por separado, solo si se decide llevarlos, con el backup anterior. Extraer en un directorio nuevo. Conservar los permisos ejecutables en Linux o llamar al script con `sh scripts/dev`. No copiar entornos virtuales, cachés, modelos o credenciales. Usar el disco local para datos y candados.

## Inspección y benchmark de HOME

En el equipo doméstico ejecutar primero `python scripts/home-inspect.py`. Informa de SO, RAM, espacio y GPU/driver/memoria. Confirmar allí la RTX 4070 Super y la RAM real. Seguir los escalones de [HARDWARE](HARDWARE.md) y acordar por separado los pesos, sus licencias y las descargas. Comprobar para cada archivo su fuente oficial, versión, hash y condiciones de uso comercial. El registro de candidatos de la biblioteca conserva esa información y nunca activa inferencia por sí mismo.

El comando `python -m integrations.home MANIFEST.json DIRECTORIO_NUEVO` está preparado para servidores locales ya instalados. Acepta las etapas `script`, `image` y `clip`. En HOME hay que verificar las versiones concretas contra los contratos. Iniciar Ollama con la nube desactivada en el proceso servidor y ComfyUI en loopback sin nodos de red. Operar sin salida a Internet y usar una instancia exclusiva. [Configuración local de Ollama](https://docs.ollama.com/faq).

| Campos del manifest | Contenido requerido en la máquina real |
|---|---|
| profile, stage, offline_confirmed | home16 o home32 según inventario, etapa elegida y confirmación del modo offline |
| source_url, version, license_id, reviewer, commercial_verified | URL oficial, versión, licencia concreta, revisor y afirmación humana sobre uso comercial. Para condiciones específicas, usar LicenseRef con el campo restrictions y el texto revisado |
| weights_path, weights_sha256, license_path, license_sha256 | Rutas de los archivos locales y hashes medidos de pesos y texto de licencia |
| model, model_digest, idea | Para Ollama, tag y digest de su manifest instalado y el brief; el digest del manifest y el hash del archivo de pesos tienen significados distintos |
| workflow_path, workflow_sha256, additional_assets | Para ComfyUI, grafo API revisado y su hash. Cada checkpoint, UNet, CLIP, VAE y referencia de entrada debe tener su registro verificado. Los nombres de los loaders deben corresponder a los archivos de la instalación revisada |
| timeout_seconds | Para imagen/vídeo, plazo acotado entre 10 y 1800 s. El prefijo de salida del grafo debe escribir en la raíz de output y usar PNG o MP4 según la etapa |

Se consultan los nodos de la instancia y el historial por ID. La cola GPU del benchmark es exclusiva entre ejecuciones del proyecto. El informe registra duración, bytes, hash, fallos y máximos **muestreados** de RAM del sistema y VRAM del dispositivo. Estos incluyen otros procesos. Para un clip se inspecciona además la duración real de 3–5 segundos con ffprobe. Ollama recibe keep_alive=0 y ComfyUI recibe una petición de liberación tras completar la etapa. Tras error o timeout, reconciliar el ID en el historial y comprobar VRAM libre antes de repetir. No se hacen reintentos automáticos ni descargas.

En casa ejecutar primero guion, imagen y un clip. Solo al superar esos pasos evaluar los cinco planos, continuidad con el mismo personaje, audio, montaje y revisión humana. Registrar también seed, versión de workflow, errores/OOM y rúbrica. El tutorial oficial del modelo Wan describe los pesos necesarios; elegir resolución y modelo tras medir el equipo. [Workflow nativo Wan 2.2](https://docs.comfy.org/tutorials/video/wan/wan2_2).

El dashboard actual sigue siendo el estudio WORK. Los clientes de benchmark HOME son independientes. Conectar un proveedor real al flujo de producción requiere primero evidencia de compatibilidad, recursos y licencias en la RTX.
