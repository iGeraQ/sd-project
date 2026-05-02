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

## Getting Started (Guía de Inicio)

Sigue estos pasos para levantar el entorno de desarrollo local:

### 1. Prerrequisitos
- [Docker](https://www.docker.com/) y Docker Compose instalados.
- (Opcional) [Poetry](https://python-poetry.org/) si deseas gestionar dependencias o ejecutar el backend sin Docker.

### 2. Configuración de Entorno
Clona el repositorio y configura las variables de entorno del backend:

```bash
# Entrar al directorio del backend
cd backend

# Copiar el archivo de variables de entorno de ejemplo
cp .env.example .env
```

> [!IMPORTANT]
> El archivo `.env.example` solo contiene una plantilla. Para obtener los valores reales de las credenciales de la base de datos, secretos JWT, keys de encriptación y claves API (ej. Resend), **debes solicitar los valores directamente al dueño del repositorio**, ya que por motivos de seguridad no se versionan en Git.

### 3. Levantar los Servicios
Regresa a la raíz del monorepo y levanta los servicios usando Docker Compose:

```bash
cd ..
docker compose up --build
```

Esto levantará:
- **Base de Datos PostgreSQL**: Puerto `5432`
- **Backend FastAPI**: Puerto `8000` con recarga automática activada (Hot-Reload).

### 4. Uso y Endpoints Útiles
Una vez que los contenedores estén corriendo, la API estará disponible localmente.

- **Documentación Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Documentación ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

### 5. Pruebas Automatizadas
El proyecto incluye un robusto set de pruebas unitarias, E2E y de regresión configuradas con `pytest`.

Para correr la suite completa de pruebas dentro del contenedor de la API:

```bash
docker compose exec api poetry run pytest -v
```

Las pruebas crearán automáticamente una base de datos efímera (`mediapp_test`) en PostgreSQL para no afectar los datos de desarrollo.
