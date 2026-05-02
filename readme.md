# MediApp - Sistema de Gestión de Citas Médicas

Este repositorio está estructurado como un **monorepo**, conteniendo tanto el backend como el frontend (y cualquier otro microservicio o capa necesaria para la plataforma).

## Documentación

Toda la documentación técnica, diagramas de arquitectura, decisiones de diseño de la base de datos y el plan de implementación por fases se encuentran en el directorio `docs/`.

Te recomendamos revisar los siguientes documentos para entender el sistema:
- [01_arquitectura.md](./docs/01_arquitectura.md) - Arquitectura general del sistema.
- [02_base_datos.md](./docs/02_base_datos.md) - Diseño, esquemas y roles de la base de datos PostgreSQL.
- [03_servicios_web.md](./docs/03_servicios_web.md) - Especificación y contratos de los servicios web (API).
- [04_concurrencia.md](./docs/04_concurrencia.md) - Estrategias de concurrencia y bloqueos para disponibilidad.
- [05_seguridad.md](./docs/05_seguridad.md) - Protocolos de seguridad, autenticación (JWT) y encriptación.
- [06_interfaz_estructura.md](./docs/06_interfaz_estructura.md) - Estructura de la interfaz de usuario.
- [07_plan_fases.md](./docs/07_plan_fases.md) - Roadmap detallado de desarrollo del backend.

## Estructura del Monorepo

- `/backend`: API RESTful construida con FastAPI, Python, SQLAlchemy (async) y PostgreSQL.
- `/docs`: Documentación centralizada del proyecto.
- `docker-compose.yml`: Orquestación de contenedores para levantar el entorno de desarrollo local.
