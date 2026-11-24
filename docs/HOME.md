# HOME · Windows y RTX 4070 SUPER

Configuración del 24-11-2026. Windows 11 Pro 10.0.26200, driver 591.86,
12282 MiB de VRAM y 15,9 GiB de RAM física. Perfil HOME16. E: tenía unos
516 GiB libres al comenzar; C: unos 14 GiB. Entornos, pesos, cachés, datos y
renders se guardan en `E:\AI-Creative-Studio`. No se modificaron drivers.

## Operación

Desde PowerShell en la raíz del repositorio:

```powershell
.\estudio.cmd start
.\estudio.cmd status
.\estudio.cmd test
.\estudio.cmd stop
```

Con doble clic en `estudio.cmd` también se abre el navegador. `start studio`,
`start ollama`, `start comfy` o `start network` permiten arrancar solo un servicio. Las mismas
opciones sirven para `stop` y `status`. El lanzador conserva PID, fecha de
creación y argumentos en `run/processes.json`; se niega a sustituir un proceso
ajeno que ocupe un puerto. Solo termina procesos gestionados y sus hijos.

| Servicio | Dirección | Uso |
|---|---|---|
| Estudio y API | http://127.0.0.1:8765/studio | Dashboard con selección MOCK / HOME real |
| ComfyUI | http://127.0.0.1:8188 | Modelos reales, workflows nativos |
| Ollama | http://127.0.0.1:11434/api/version | API LLM local |
| Proxy de denegación | http://127.0.0.1:8767/health | Bloquea HTTP/CONNECT externo de Ollama; no reenvía tráfico |

Los datos de la aplicación están en `E:\AI-Creative-Studio\data`. Retrobay y
Exyo están creadas. Esta copia del repositorio no contenía la base ni los blobs
del piloto WORK anterior; no se han inventado ni recreado sus identificadores.

El lanzador usa `STUDIO_PROFILE=home16`, `STUDIO_ENABLE_HOME=1` y una raíz HOME
absoluta. WORK bloquea inferencia incluso si se intenta combinar con el opt-in.
Al arrancar todos los servicios, Ollama y ComfyUI arrancan antes que el estudio;
al detenerlos, el estudio se detiene primero. La migración a Next.js, FastAPI y
Temporal sigue separada del ejecutable reducido actual.

## Producción real desde el dashboard

Crear una campaña y pulsar **Nueva producción** en el estudio. Elegir proveedor
**HOME**, idea, preset y ficha de personaje. Al pulsar **Renderizar reel** se
genera el guion mediante Ollama, una referencia SDXL y cinco planos Wan I2V con
esa referencia común. La ficha de personaje aporta nombre y descripción; las
vistas de la biblioteca son procedurales MOCK, sin IP-Adapter ni LoRA instalados.
Los presets condicionan el prompt; no garantizan una estética ni continuidad.

El perfil probado usa planos de tres segundos y 480 × 832, carga FP8 del peso
FP16, batch uno y exportación escalada/recortada a 1080 × 1920. La interfaz limita
la duración HOME a ese perfil. WORK conserva planos de 3–5 segundos simulados.
No existe fallback a MOCK o a inferencia remota al fallar HOME.

Los checkpoints, IDs, grafos API, versiones de pesos, hashes, recursos y errores
se guardan en el documento SQL de producción. Los blobs de guion/referencia,
clips, montajes y textos de licencia quedan en `data/blobs`. No hay transacciones
SQL abiertas durante inferencia ni una shell controlada por el modelo.

**Cancelar render** solicita cancelación atómica del ID concreto al ComfyUI
0.46.0 auditado. Conserva candidatos ya guardados. **Reintentar / reanudar**
consulta cola e historial antes de enviar nada nuevo. Si un clip sigue activo
al reiniciar el estudio, se recoge el mismo ID. Si ComfyUI perdió su historial y
no se puede confirmar el resultado, la producción se detiene como incierta;
un reintento explícito se limita a dos intentos de proveedor por etapa/versión.
No se promete recuperar latentes al reiniciar ComfyUI ni exactamente una ejecución
en cualquier fallo distribuido. La cola implementada es SQL y candado del SO,
no Temporal. Las herramientas CLI comparten el candado GPU.

La regeneración conserva los candidatos anteriores y no modifica otros planos.
Editar, reordenar, seleccionar o regenerar invalida la revisión ligada al montaje.
Los errores de memoria, proveedor, respuesta truncada y timeout se muestran;
el worker no reintenta inferencia fallida sin una acción explícita del operador.
Una petición de guion interrumpida por reinicio puede repetirse de forma acotada:
no genera una publicación ni otro efecto externo persistente.

El [piloto integrado](http://127.0.0.1:8765/studio?brand=720c761b-64d9-4d3c-9dd5-b1dc2e82edeb&production=add9f514-9e1f-4a68-b5e4-c537bd124318#edit)
está listo para revisión. Tiene cinco clips, dos candidatos del tercer plano,
audio procedural, subtítulos, portada y manifest. SHA-256 del vídeo vigente:
`b9da7f32b738b74edd1fd90cc278515c9bb4813262417dd60a1e4ac68703b906`.
No tiene revisiones ni publicaciones. La exportación legible está en
`E:\AI-Creative-Studio\exports\dashboard-retrobay-20261124`.

La copia `backups/dashboard-home-20261124` contiene 21 blobs referenciados y se
restauró en `backups/dashboard-home-restored-20261124`. El vídeo y cinco textos
de licencia conservaron sus hashes. Estos datos HOME integrados sí pertenecen al
backup SQLite/blobs existente. Los renders de las herramientas CLI antiguas, sus
pesos y entornos siguen fuera de ese backup y se conservan por separado.

## Instalado y fijado

| Pieza | Versión / fuente |
|---|---|
| Python aislado | CPython 3.12.14 mediante uv 0.12.18, ya disponible en el equipo |
| Backend | Pydantic 2.14.4, tzdata 2026.6, pytest 9.2.0, Ruff 0.17.6; lock completo en la raíz |
| Ollama portable | [v0.40.18 oficial](https://github.com/ollama/ollama/releases/tag/v0.40.18), MIT y avisos de dependencias |
| ComfyUI | [v0.46.0 / a277b5bf213e8a44fa34817b7770b54f86ef4cea](https://github.com/Comfy-Org/ComfyUI/tree/a277b5bf213e8a44fa34817b7770b54f86ef4cea), GPL-3.0 |
| Comfy frontend / aimdo | 1.59.6 / 0.6.0, GPL-3.0; textos oficiales/locales inspeccionados |
| PyTorch | 2.14.1+cu130, torchvision 0.29.1+cu130, torchaudio 2.11.0+cu130; imports y GPU comprobados |
| FFmpeg / ffprobe | [9.1 essentials de Gyan](https://github.com/GyanD/codexffmpeg/releases/tag/9.1), compilación GPL-3.0 con libx264 y AAC |
| Navegador de pruebas | Playwright Core 1.65.1 en E:, Chrome existente 158.0.8127.37 |

SHA-256 del ZIP Ollama:
`ca97292ac1e9acc77fcf473bb2741fa6acd12e3798f261b419680068b7cc4c16`.
SHA-256 del ZIP FFmpeg:
`b9bbbb3acece000cbeec994f856649354e52c773807841e78908374b24d658fd`.
Ambos se compararon con los digests publicados por GitHub antes de extraerlos.

El inventario `E:\AI-Creative-Studio\installation.json` registra URLs, versiones,
hashes de archivos de licencia, archivos RECORD de paquetes y fuentes del proyecto.
Incluye 14 distribuciones del entorno de aplicación y 86 del entorno ComfyUI.
Las declaraciones de licencia de paquetes se obtienen de sus metadatos; los
dos paquetes Comfy sin declaración suficiente se contrastaron con sus textos
oficiales. Esto no es una auditoría exhaustiva de cada dependencia vendorizada.
No se redistribuyen binarios. Sus licencias y las obligaciones de redistribución
deben conservarse si más adelante se empaqueta el software.

## Pesos y licencias

| Peso | Tamaño del archivo | Licencia y revisión |
|---|---|---|
| [Qwen3 4B Q4_K_M](https://ollama.com/library/qwen3:4b) | 2.497.280.480 bytes | Apache-2.0; manifest original y GGUF verificados |
| [SDXL base 1.0](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0) | 6.938.078.334 bytes | CreativeML Open RAIL++-M; uso sujeto al anexo A y derechos de terceros |
| [Wan 2.2 TI2V 5B FP16](https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged) | 9.999.658.848 bytes | Apache-2.0; repack oficial recomendado por ComfyUI |
| uMT5 XXL FP8 scaled | 6.735.906.897 bytes | Apache-2.0, [modelo original de Google](https://huggingface.co/google/umt5-xxl), repack Comfy-Org |
| Wan 2.2 VAE | 1.409.400.960 bytes | Apache-2.0, mismo repack Wan |

Las revisiones exactas, URLs fijadas, tamaños y hashes esperados de ComfyUI
están en `config/home-assets.json`. El registro local
`licenses/verified-assets.json` añade rutas reales, hash del texto de licencia,
revisor y restricciones. Los manifests del benchmark comprueban esos hashes
antes de activar un peso. No se descargaron LoRA, fuentes, música o referencias
visuales ajenas. Qwen2.5 3B se descartó por su licencia Research; LTX 0.9.8 se
descartó como opción predeterminada por la condición comercial de facturación.

## Herramientas CLI de diagnóstico y piloto anterior

```powershell
.\estudio.cmd prepare
.\estudio.cmd benchmark --stage script
.\estudio.cmd benchmark --stage image
.\estudio.cmd benchmark --stage clip
.\estudio.cmd reel
```

`prepare` fija workflows por hash, verifica pesos y comprueba los argumentos
offline de ComfyUI. `benchmark` nunca descarga. Cada ejecución crea un directorio
nuevo en `benchmarks`, con artefacto y `benchmark.json`. El acceso cooperativo
de estas herramientas a GPU es exclusivo; se rechazan trabajos si ComfyUI tiene
cola o si Ollama conserva un modelo cargado. No ejecutar inferencia manual por
otras aplicaciones al mismo tiempo. Los límites de este candado no alcanzan
otros programas que no lo respeten.

El piloto utiliza el último guion y la última imagen de benchmarks completados,
verifica sus hashes y genera cinco planos I2V con esa misma referencia. Cada
plano usa 73 frames a 24 fps y se recorta a tres segundos. El montaje de 15 s se
exporta a 1080 × 1920 con H.264, AAC y subtítulos mov_text. La resolución nativa
es **480 × 832**, escalada para la exportación; no representa detalle nativo Full HD.
El primer piloto de diagnóstico a 288 × 512 se conserva separado y presenta
artefactos visibles. El preset actual carga el modelo FP16 en FP8 para limitar
memoria; los pesos originales y su hash se conservan.
El sonido son tonos originales procedurales, sin grabaciones ni música ajenas.

Los resultados quedan en `reels/retrobay-FECHA-HORA`. Los manifests conservan
seeds, referencia, workflows, hashes, recursos, QC y `human_review=pending`.
Es una herramienta de piloto secuencial por CLI; no es todavía un worker GPU
durable integrado en el dashboard. Si falla, conserva los planos y diagnósticos,
pero repetir el comando inicia un piloto nuevo. El control de calidad técnico
no aprueba identidad, continuidad, manos, movimiento o narrativa.

El piloto CLI anterior está en
`E:\AI-Creative-Studio\reels\retrobay-20261124-164623\reel.mp4`, junto a portada,
audio, subtítulos, workflows, cinco clips e informes. Sus cinco benchmarks
completaron y el montaje pasó QC técnico. Tiene 15 s y 9.051.787 bytes; SHA-256
`4d25a880743232f94e8e6e959955898d509da68948203ce8678b216d7a78abf6`.
La suma de etapas medidas es 432,814 s, sin contar verificación previa de pesos
ni montaje. Las muestras máximas fueron 11422 MiB VRAM y 11030 MiB RAM del
sistema. Sigue pendiente de revisión humana; no se ha publicado.

## Red, memoria y límites

Ollama se inicia con `OLLAMA_NO_CLOUD=1`, una sola carga y una sola inferencia;
el cliente solicita descarga de memoria con `keep_alive=0`. ComfyUI arranca con
`--offline`, `--disable-all-custom-nodes`, `--reserve-vram 1.5` y `--fast-disk`.
Su frontend aplica CSP restrictiva y desactiva nodos de API; Hugging Face y
Transformers se configuran offline. Los clientes del proyecto solo conectan a
127.0.0.1 y no contienen fallback remoto. No hay descargas al arrancar.

Studio y ComfyUI se ejecutan con una política Python que permite sockets de
salida solo a loopback. El lanzador fija HTTP_PROXY/HTTPS_PROXY/ALL_PROXY a un
proxy de denegación en 127.0.0.1:8767 y NO_PROXY a loopback. La prueba real de
`/api/pull` fue bloqueada y no cambió el inventario. Para instalar se necesita
arrancar Ollama explícitamente con `--allow-downloads`; producción rechaza ese
modo. Estas medidas no modifican la red del sistema ni aíslan código nativo.

No se cambiaron reglas de firewall ni se desconectó físicamente la red. Durante
la observación de procesos locales no aparecieron conexiones externas de los
proveedores. Esta muestra no acredita aislamiento de red a nivel de sistema
operativo. Se puede producir con la conexión desconectada una vez instalados
los pesos; esa prueba física queda pendiente.

Los máximos de RAM/VRAM son muestras de todo el sistema/dispositivo cada segundo,
no mediciones exclusivas del modelo ni garantías de pico absoluto. Mantener el
perfil medido y cerrar programas pesados si falta memoria. 480 × 832 superó la
prueba técnica; 720p y modelos 14B no se han probado. No hay reintentos automáticos de
inferencia. Ante timeout se cancela el ID concreto y se solicita liberar memoria;
comprobar la cola antes de repetir. La publicación sigue desactivada.

## Reproducir instalación y comprobaciones

Los scripts POSIX originales se conservan. En Windows se usa el lanzador CMD,
sin cambiar ExecutionPolicy. Para recrear entornos en un destino nuevo con uv:

```powershell
$env:UV_PYTHON_INSTALL_DIR='E:\AI-Creative-Studio\python'
$env:UV_CACHE_DIR='E:\AI-Creative-Studio\cache\uv'
uv python install 3.12.14
uv venv E:\AI-Creative-Studio\venvs\studio --python 3.12.14
uv pip install --python E:\AI-Creative-Studio\venvs\studio\Scripts\python.exe -r requirements-home.lock
git clone --depth 1 --branch v0.46.0 https://github.com/Comfy-Org/ComfyUI.git E:\AI-Creative-Studio\ComfyUI
uv venv E:\AI-Creative-Studio\venvs\comfy --python 3.12.14
uv pip install --python E:\AI-Creative-Studio\venvs\comfy\Scripts\python.exe --extra-index-url https://download.pytorch.org/whl/cu130 -r requirements-comfy-home.lock
```

En ese destino nuevo, descargar los ZIP oficiales de la tabla, comparar sus
SHA-256 y extraer Ollama en `ollama/` y FFmpeg en `ffmpeg/`, conservando la carpeta
`ffmpeg-9.1-essentials_build`. Crear `tmp/` y `logs/`. Después, con descargas de
modelos expresamente decididas, ejecutar:

```powershell
E:\AI-Creative-Studio\venvs\studio\Scripts\python.exe scripts/home-download.py E:\AI-Creative-Studio
# Descarga de instalación explícita, nunca al producir:
.\estudio.cmd stop ollama
.\estudio.cmd start ollama --allow-downloads
E:\AI-Creative-Studio\ollama\ollama.exe pull qwen3:4b
.\estudio.cmd stop ollama
.\estudio.cmd start
.\estudio.cmd prepare
```

El tag Qwen debe resolver al digest
`359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7` para
reproducir esta medición. Si cambia, revisar el peso y su licencia de nuevo.
Los entornos backend y ComfyUI son independientes. No copiar venv entre equipos.
`STUDIO_HOME_ROOT` permite usar otra raíz sin editar el repositorio.

`estudio.cmd test` ejecuta pytest y sintaxis JS. El recorrido de navegador usa
Node y requiere `PLAYWRIGHT_CORE`, `CHROMIUM_PATH` y `STUDIO_PYTHON` apuntando a
las instalaciones locales; ejecutar `node tests/dashboard.mjs`. En este equipo
Playwright se instaló con `npm install --prefix E:\AI-Creative-Studio\tools\browser
--ignore-scripts --no-fund --no-audit --save-exact playwright-core@1.65.1`.
El inventario se regenera con `python scripts/home-inventory.py RAIZ_HOME`.
PostgreSQL, Temporal, Next.js y FastAPI no se instalaron: no son dependencias del
ejecutable actual y el perfil reducido evita añadir servicios en los 16 GB.

## Auditoría de endurecimiento

El [informe del 24-11-2026](AUDIT-2026-11-24.md) recoge 33 pruebas aprobadas,
smoke real de Qwen/SDXL/Wan, recorrido WORK/HOME y recuperación sin historial
mediante metadata del workflow. Esta última prueba usa una copia restaurada,
checkpoint reconstruido y clip auténtico, con el mismo hash y cero nuevos POST.
No acredita un corte real de alimentación. Ante salida corrupta, ambigua o sin
grafo y referencia verificables, se conserva el error visible.

Los resultados se guardan antes de liberar memoria; un error de cleanup no
revierte un clip confirmado. Las rutas de carga, argumentos de ComfyUI y textos
de licencia están fijados. Cambiar estos elementos exige revisión explícita y
no se acepta como una actualización transparente de los modelos.
