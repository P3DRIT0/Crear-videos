# ADR 006 · Fuentes públicas y adaptadores

Consulta anónima de metadatos de GitHub. La fecha corresponde al último push informado y el enlace fija el commit consultado. SHA-256 identifica el archivo de licencia obtenido. Las licencias de pesos y assets se comprueban por separado antes de habilitarlos.

| Fuente y versión | Último push | SPDX declarado | SHA-256 de la licencia |
|---|---|---|---|
| [msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents/tree/8ae6164602c95ca78828b148b9052460ee426885) | 2026-11-09 | MIT | 9a45258434d5cedf0af73c9ad4771373701225038d246c49219026c33677f66f |
| [sergebulaev/instagram-skills](https://github.com/sergebulaev/instagram-skills/tree/823c681b42be9ecff9f4db20eaf14d1ea45ec1a1) | 2026-11-18 | MIT | 1a21cf7c208981ef516dcf2edb4517dab907b8dc94c2cfc523565c794ea8e148 |
| [neuregex/freefield](https://github.com/neuregex/freefield/tree/e29b7c913149efe7739d19d3b1c608e32e27e6d7) | 2026-11-24 | MIT | 7f0e629ca831057bc4750e109ee8bb5be7f9385e85356a72a4a20b3a6f40decc |
| [thePloggy/CreatorOS-Studio](https://github.com/thePloggy/CreatorOS-Studio/tree/b94a6b3e1eda6eaa9a7108b219bb62513049f023) | 2026-11-13 | Apache-2.0 | cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30 |
| [hollisorg/iv-studio](https://github.com/hollisorg/iv-studio/tree/bf1a71583f9ca642c4164418b12f6d44a065244d) | 2026-11-24 | MIT | 55e068e8354dc396cdc2f36ad9b8dc870ce9c8ed303fd4f506ee37e51bc222c8 |
| [Comfy-Org/ComfyUI](https://github.com/Comfy-Org/ComfyUI/tree/da8bd08e48deee74d9f6c3bc00aed365b00ec209) | 2026-11-24 | GPL-3.0 | 3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986 |
| [ollama/ollama](https://github.com/ollama/ollama/tree/924cc286cc592f49c481fa84e15fa60dbc75989e) | 2026-11-24 | MIT | 5934ed2ce0d15154bcdb9c85203210abac0da4314af34081e36df4599f90b226 |
| [gitroomhq/postiz-app](https://github.com/gitroomhq/postiz-app/tree/44df988cb1840dc5eb50755536b3e6e326d27fc3) | 2026-11-24 | AGPL-3.0 | d322fb1066693d8ed25495d11029f443aa793316852749e1389773c1946251b3 |
| [Wan-Video/Wan2.2](https://github.com/Wan-Video/Wan2.2/tree/1ea34ff48f87168174e12956e200b1d908b1c5ff) | 2026-09-21 | Apache-2.0 | c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4 |
| [lllyasviel/FramePack](https://github.com/lllyasviel/FramePack/tree/97fe5dbe06ac1f337ece08935b1076a35eefeeb9) | 2025-10-16 | Apache-2.0 | c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4 |
| [Lightricks/LTX-Video](https://github.com/Lightricks/LTX-Video/tree/50f0aef1297574a4b29acbdb874e3a363a6d5f2e) | 2026-11-02 | Apache-2.0 | c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4 |
| [ToonCrafter/ToonCrafter](https://github.com/ToonCrafter/ToonCrafter/tree/b0c47ff339c5e5ec45b84d0c6587850f242d41ef) | 2025-03-19 | Apache-2.0 | 9849d33ce88d14d755c8d71d7c8e6deecf7e9ff8d91a6ca0ee5cd9058120b830 |
| [hexgrad/kokoro](https://github.com/hexgrad/kokoro/tree/dfb907a02bba8152ca444717ca5d78747ccb4bec) | 2025-08-06 | Apache-2.0 | c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4 |
| [resemble-ai/chatterbox](https://github.com/resemble-ai/chatterbox/tree/ab55923c27757c90cfcc407baa57dc25a7d25217) | 2026-11-04 | MIT | 4248e910a928849fe5815a0f9236e17fa07768d95b9193212752c464b93d6caa |
| [FFmpeg/FFmpeg](https://github.com/FFmpeg/FFmpeg/tree/9ec5cf1aac6ac402df6934cc3bcd825c4cfe1220) | 2026-11-24 | NOASSERTION | e6dc72d5665a1ebd6dcc841de59278dad4ca77ecc47b03f1064a55c3e9ea8bb8 |

## Decisiones de reutilización

- Agency Agents e Instagram Skills se consultaron como referencias de separación de roles, entregables, copy y calendario. Los roles y las plantillas del proyecto son propios. La ruta de publicación con Publora queda fuera de WORK. [Agency Agents](https://github.com/msitarzewski/agency-agents) y [Instagram Skills](https://github.com/sergebulaev/instagram-skills).
- Freefield combina manifests, grafos ComfyUI, gateway y opciones de ejecución remota. CreatorOS enlaza un servidor Fastify con ComfyUI por HTTP/WebSocket y modifica recetas en memoria. IV Studio declara rutas locales y opciones de nube y de pago. Se adopta la idea de fijar recetas por hash. Ningún workflow upstream se ha importado: primero habrá que verificar nodos, pesos y licencia en HOME. [Freefield](https://github.com/neuregex/freefield), [CreatorOS](https://github.com/thePloggy/CreatorOS-Studio) e [IV Studio](https://github.com/hollisorg/iv-studio).
- El cliente experimental de ComfyUI usa envío por /prompt, lectura de historial por ID y descarga local por /view. La cancelación individual elimina una entrada pendiente de la cola. La interrupción global de inferencia activa requiere un worker dedicado. Ollama recibe un esquema JSON en /api/chat y debe tener ya el modelo local con el digest esperado. Se prueba el transporte mediante fixtures loopback. La interoperabilidad con un servidor instalado se comprueba en HOME. [ComfyUI](https://docs.comfy.org/development/comfyui-server/comms_routes) y [Ollama](https://docs.ollama.com/api/chat).
- FFmpeg se utiliza como ejecutable ya instalado con argumentos fijos. El licenciamiento de la compilación concreta depende de sus opciones. Registrar `ffmpeg -L` y `ffmpeg -buildconf` antes de redistribuir cualquier binario. Aquí únicamente se exporta material procedural propio. [Licencias de FFmpeg](https://www.ffmpeg.org/legal.html).

## Contrato futuro de publicación real

El adaptador recibe marca, hash exacto con revisión humana, licencia y destino autorizado. El publisher debe denegar material simulado antes de abrir conexiones. Ante respuesta incierta conservar el identificador del contenedor o post y consultar su estado antes de cualquier nuevo intento. La simulación local confirma su estado en una única transacción y una clave única por producción y hash permite reconciliar repeticiones.

Meta requiere cuenta profesional y autorización. Con Instagram Login se documentan instagram_business_basic e instagram_business_content_publish. Facebook Login tiene otros permisos y vinculación con página. Comprobar Standard/Advanced Access y revisión de la app según usuarios y flujo antes de una integración. El flujo por URL necesita un medio accesible para Meta y la documentación contempla subida reanudable en los flujos que la soportan. No exponer automáticamente el equipo. [Guía oficial de publicación](https://developers.facebook.com/documentation/instagram-platform/content-publishing).

Postiz usa una integración conectada mediante OAuth. Su API de posts requiere credencial, identificador de integración y, para programar, una fecha. La futura opción autohospedada exigiría validar la configuración de Instagram, los medios y la licencia del despliegue. Este proyecto solo implementa el destino local dry-run. [Creación de posts](https://docs.postiz.com/public-api/posts/create) y [repositorio oficial](https://github.com/gitroomhq/postiz-app).
