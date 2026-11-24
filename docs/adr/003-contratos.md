# ADR 003 · API, identidad y almacenamiento
Aceptada para la fase 01 el 24-11-2026.

API JSON versionada bajo /api/v1, UUID canónicos, fechas UTC en disco y Europe/Madrid en pantalla. Catálogo de marcas con Retrobay de ejemplo. Campañas y jobs se consultan, crean, modifican y borran dentro de una marca. Un job referencia una campaña de la misma marca. Rechazar el borrado de campañas con jobs. Estado inicial pending; la ejecución manual termina en succeeded o failed. Permitir editar la etiqueta mientras está pendiente y volver a ejecutar tras fallo. Los resultados confirmados son inmutables.

POST de creación exige Idempotency-Key con UUID y registra petición y respuesta en la misma transacción. La reutilización con otro cuerpo u operación en la misma marca produce 409. PATCH asigna valores absolutos. Una segunda ejecución exitosa devuelve el job y el hash ya confirmados. El acceso a la ficha se resuelve por marca e ID de job, nunca por una ruta aportada por el cliente. Los bytes son JSON UTF-8 canónico con versión, marca, campaña y objetivo. No hay contenido generado por IA.

El documento OpenAPI servido y los modelos de packages/contracts forman el contrato de la slice. Los esquemas de las fases futuras permanecen como propuestas. Los errores tienen código y mensaje; las listas tienen orden estable. La protección por marca evita referencias cruzadas, pero el proceso local no proporciona autenticación multiusuario.
