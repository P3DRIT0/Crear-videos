# ADR 007 · Configuración HOME en Windows

Fecha: 2026-11-24. Solicitud: completar en el equipo doméstico la configuración pendiente.

## Inspección y decisiones

Windows 11 Pro, RTX 4070 SUPER (12282 MiB), driver 591.86, RAM física
17054560256 bytes (15,9 GiB). C: dispone de aproximadamente 14 GiB y E: de
516 GiB. Se elige HOME16, ejecución nativa Windows y almacenamiento dedicado
`E:\AI-Creative-Studio`. No se cambian drivers, servicios del sistema ni cuentas.
El repositorio está limpio al iniciar; no hay dependencias ni datos del piloto
WORK en esta copia. El servidor existente solo admite WORK y no se confundirá
con un pipeline de inferencia real.

## Plan de cambios

1. Instalar Python 3.12 aislado, entorno backend, FFmpeg con libx264/AAC,
   Ollama portable y ComfyUI en entorno independiente. Fijar versiones y hashes.
2. Añadir arranque, parada y comprobaciones Windows reproducibles. Mantener
   SQLite y el dashboard existente; no migrar de stack durante el setup.
3. Revisar licencias de los pesos concretos antes de descargarlos. Seleccionar
   LLM pequeño, imagen y vídeo ligero; comprobar primero APIs y nodos reales.
4. Ejecutar tests de aplicación y smoke tests reales por etapa, secuenciales,
   con hashes, tiempos, recursos muestreados y diagnóstico de fallos.
5. Documentar lo instalado y los límites reales en README y STATUS. No publicar,
   aprobar contenido en nombre del usuario, hacer commits ni push.

## Criterios de aceptación

- Arranque Windows del estudio en 127.0.0.1 y health/schema/storage correctos.
- Pruebas de regresión y codificación FFmpeg, sin servicios de pago.
- Ollama sin nube y ComfyUI sin nodos de API, solo loopback, versiones fijadas.
- Cada peso activado tiene URL, revisión, tamaño, SHA-256, licencia y restricciones.
- Guion, imagen y clip se declaran operativos solo con artefactos reales medidos.
- La revisión humana y la publicación siguen siendo puertas independientes.
- Si la memoria o una dependencia impiden una etapa, registrar el fallo sin
  sustituirlo silenciosamente por material MOCK.

## Referencias verificadas durante la configuración

- https://docs.comfy.org/installation/manual_install
- https://docs.ollama.com/faq
- https://ollama.com/library/qwen3:4b (Apache-2.0, Q4_K_M, tamaño anunciado 2,5 GB)
- https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0
  (CreativeML Open RAIL++-M, permite uso sujeto a restricciones del anexo A).

Qwen2.5 3B se descarta como elección predeterminada: su licencia concreta es
Qwen Research y no Apache-2.0. Las fuentes y hashes efectivos de la instalación
se registran en el inventario local, sin incluir binarios o pesos en Git.

## Ajuste después de las primeras mediciones

SDXL y Wan 5B superaron los smoke tests. Wan FP16 a 288 × 512 mostró artefactos
visibles; el piloto inicial no se considera aprobado visualmente. Se evaluó
480 × 832 con carga `fp8_e4m3fn` del mismo archivo oficial FP16, sin nuevos pesos.
ComfyUI completó el clip de 3,04 s; la muestra de VRAM alcanzó 11607 MiB y la de
RAM 11815 MiB. El primer comando manual omitió PATH de ffprobe: se conservan el
informe fallido y la validación posterior del mismo archivo en `validation.json`.
La invocación normal del lanzador sí configura FFprobe. Se adopta esa resolución
para el piloto CLI tras esta prueba, manteniendo revisión humana pendiente y sin
habilitar 720p. No se confunde cuantización de carga con descarga de otro modelo.
