# Criterios de entrega
- Arranque limpio reproducible documentado, sin cuentas externas y sin GPU en WORK.
- Crear marca, campaña, guion estructurado, storyboard, cinco planos simulados, MP4 vertical de prueba, revisión, calendario y publicación dry-run; todos los datos MOCK visibles, ningún envío real.
- Reiniciar worker durante job y recuperar estado sin duplicación; cancelar, reintentar plano individual y conservar otros planos; fallos de proveedores visibles.
- Tests de límites de GPU, offline, licencias, aprobación ligada al hash, aislamiento multimarca, rutas seguras, secretos, publicación idempotente y reconciliación.
- HOME: smoke tests reales por proveedor, benchmark reproducible, vídeo revisado por humano, manifest de licencias, sin fallback de pago. Solo tras eso habilitar publicación real mediante autorización independiente.
- CI local gratis (scripts lint/test/build). GitHub Actions opcional, no dependencia ni consumo obligatorio de cuota. Mantener docs/STATUS.md con hecho/pendiente/bloqueado, comandos reales y resultados.
