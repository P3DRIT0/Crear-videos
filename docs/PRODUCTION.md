# Producción audiovisual

## Presets
Cinematic 3D, anime, cartoon 2D, clay/stop motion, miniature world, motion graphics y product CGI. Cada preset versiona paleta, referencias propias, composición, lentes, iluminación, movimiento, negativos, modelos compatibles y reglas de continuidad. No depender de marcas de estudios de animación. Character bible: frente/perfil/espalda, expresiones, escala, ropa, colores, poses y referencias. SDXL + IP-Adapter/ControlNet o LoRA compatible como opción de consistencia; no asumir que todos los nodos sirven con todos los modelos.

## Pipeline por plano
Idea y guion de 15–30s, 5–8 planos de 3–5s; storyboard vertical; fotogramas clave aprobados; image-to-video con referencia de personaje; candidatos limitados; seleccionar planos por continuidad, movimiento y narrativa. Audio original o con licencia, voz opcional, efectos, subtítulos SRT/ASS; montaje FFmpeg con timeline JSON, Blender para planos controlados. Interpolación y escalado opcionales, no confundir upscale con detalle nativo. Export MP4 H.264 y AAC, 1080x1920, fps uniforme 24/30, y validar requisitos vigentes de Instagram antes de publicar. Portada, copy, alt text cuando proceda, hashtags sin spam.

## QC
ffprobe: archivo legible, resolución, duración, audio, fps, ausencia de frames negros inesperados; análisis de cortes, clipping sonoro, zonas seguras de texto. Revisión visual con modelo local opcional y evaluación humana: identidad, anatomía, parpadeo, coherencia temporal, artefactos, composición y narrativa. Puntuar 1–5 por dimensión, umbral configurable, sin inventar precisión; máximo 2 regeneraciones automáticas por plano y después revisión. Licencias y afirmaciones comerciales verificadas antes de aprobar. Aprobación manual predeterminada. Autopublicación solo activada por marca tras pruebas reales y consentimiento explícito; límites diarios, ventana horaria, botón de parada.

## Modelos candidatos (validar licencia, versión, memoria y compatibilidad antes de activar)
Ollama Qwen 3.5 4B/9B cuantizado si disponible; alternativa Qwen2.5 3B/7B. SDXL, Z-Image Turbo para imágenes. Wan 2.2 TI2V-5B para clips, LTX-Video 2B y FramePack como alternativas; Wan 14B cuantizado solo experimental. ToonCrafter para interpolación de dibujos si compatible. Kokoro (validar castellano), Chatterbox opcional, ACE-Step música opcional, faster-whisper, RIFE y Real-ESRGAN. Descargar solo tras inspección de hardware; no asumir ejecución de todos los modelos con 12GB. No incluir MiniMax H3 remoto ni modelos cerrados como dependencias. Revisar modelos específicos y pesos, no solo licencia del repositorio.

## Fuentes upstream a auditar
https://github.com/Comfy-Org/ComfyUI
https://github.com/Wan-Video/Wan2.2
https://github.com/lllyasviel/FramePack
https://github.com/Lightricks/LTX-Video
https://github.com/ToonCrafter/ToonCrafter
https://github.com/ollama/ollama
https://github.com/neuregex/freefield
https://github.com/thePloggy/CreatorOS-Studio
https://github.com/hollisorg/iv-studio
https://github.com/msitarzewski/agency-agents
https://github.com/sergebulaev/instagram-skills
https://github.com/gitroomhq/postiz-app
https://github.com/hexgrad/kokoro
https://github.com/resemble-ai/chatterbox
https://github.com/FFmpeg/FFmpeg
Los enlaces son candidatos, no integraciones verificadas en este paquete. Confirmar existencia, actividad, licencia, API real y dependencias. No ejecutar instaladores de terceros sin inspección. Registrar ADR: adoptar, reutilizar workflow, o descartar.
