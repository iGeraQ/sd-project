# 4. Especificación de Servicios Web (API REST)

## 4.1 Convenciones Generales

| Aspecto | Especificación |
|---------|---------------|
| **Protocolo** | HTTPS |
| **Base URL** | `https://api.mediapp.com/api/v1` |
| **Formato de datos** | JSON (`Content-Type: application/json`) |
| **Autenticación** | Bearer Token JWT en header `Authorization` |
| **Códigos de estado** | 200 (OK), 201 (Created), 400 (Bad Request), 401 (Unauthorized), 403 (Forbidden), 404 (Not Found), 409 (Conflict), 500 (Internal Error) |
| **Paginación** | Query params `?page=1&limit=20` |

### Formato de Respuesta Estándar
```json
{
  "success": true,
  "data": { },
  "message": "Operación exitosa",
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 100,
    "totalPages": 5
  }
}
```

### Formato de Error Estándar
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Descripción del error",
    "details": []
  }
}
```

---

## 4.2 Servicios de Autenticación

### `POST /auth/register` — Registro de usuario (paciente)
**Acceso:** Público

**Request Body:**
```json
{
  "username": "juan.perez",
  "password": "SecurePass123!",
  "nombre": "Juan Pérez García",
  "direccion": "Calle Reforma 123, CDMX",
  "correo_electronico": "juan@email.com",
  "telefono": "5551234567",
  "edad": 35,
  "sexo": "masculino"
}
```

**Validaciones:**
- `username`: 4-50 caracteres, único, alfanumérico + puntos
- `password`: mínimo 8 caracteres, 1 mayúscula, 1 número, 1 especial
- `correo_electronico`: formato email válido
- `edad`: entero 1-149
- `sexo`: "masculino" | "femenino" | "otro"

**Response (201):**
```json
{
  "success": true,
  "data": {
    "id": 1,
    "username": "juan.perez",
    "rol": "paciente",
    "token": "eyJhbGciOiJIUzI1NiIs..."
  }
}
```

---

### `POST /auth/login` — Inicio de sesión
**Acceso:** Público

**Request Body:**
```json
{
  "username": "juan.perez",
  "password": "SecurePass123!"
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIs...",
    "usuario": {
      "id": 1,
      "username": "juan.perez",
      "rol": "paciente",
      "nombre": "Juan Pérez García"
    },
    "expiresIn": 86400
  }
}
```

**Estructura del JWT Payload:**
```json
{
  "sub": 1,
  "username": "juan.perez",
  "rol": "paciente",
  "iat": 1714610000,
  "exp": 1714696400
}
```

---

## 4.3 Servicios de Gestión de Pacientes

### `GET /pacientes` — Lista de pacientes
**Acceso:** Médico  
**Query Params:** `?page=1&limit=20&buscar=Juan`

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "nombre": "Juan Pérez García",
      "correo_electronico": "juan@email.com",
      "telefono": "5551234567",
      "edad": 35,
      "sexo": "masculino"
    }
  ],
  "pagination": { "page": 1, "limit": 20, "total": 1 }
}
```

### `GET /pacientes/:id` — Detalle de paciente
**Acceso:** Médico o el propio Paciente

### `PUT /pacientes/:id` — Actualizar paciente
**Acceso:** El propio Paciente o Médico

**Request Body (parcial):**
```json
{
  "direccion": "Nueva dirección 456",
  "telefono": "5559876543"
}
```

### `DELETE /pacientes/:id` — Eliminar paciente
**Acceso:** Médico

---

## 4.4 Servicios de Gestión de Citas

### `GET /horarios` — Horarios disponibles
**Acceso:** Paciente, Médico  
**Query Params:** `?fecha=2026-05-15&medico_id=1`

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "id": 10,
      "fecha": "2026-05-15",
      "hora_inicio": "09:00",
      "hora_fin": "09:30",
      "disponible": true,
      "version": 1
    },
    {
      "id": 11,
      "fecha": "2026-05-15",
      "hora_inicio": "09:30",
      "hora_fin": "10:00",
      "disponible": true,
      "version": 1
    }
  ]
}
```

### `POST /citas` — Crear nueva cita ⚡ (Con control de concurrencia)
**Acceso:** Paciente, Médico

**Request Body (por Paciente):**
```json
{
  "horario_id": 10,
  "motivo_consulta": "Dolor de cabeza persistente",
  "horario_version": 1
}
```

**Request Body (por Médico — para un paciente):**
```json
{
  "paciente_id": 5,
  "horario_id": 10,
  "motivo_consulta": "Control de seguimiento",
  "horario_version": 1
}
```

> **Nota:** El campo `horario_version` es obligatorio para el mecanismo de exclusión mutua (ver Sección 6).

**Response (201):**
```json
{
  "success": true,
  "data": {
    "id": 25,
    "paciente_id": 5,
    "medico_id": 1,
    "horario": {
      "fecha": "2026-05-15",
      "hora_inicio": "09:00",
      "hora_fin": "09:30"
    },
    "estado": "programada",
    "creado_por": "paciente"
  },
  "message": "Cita reservada exitosamente"
}
```

**Error de Concurrencia (409):**
```json
{
  "success": false,
  "error": {
    "code": "HORARIO_NO_DISPONIBLE",
    "message": "El horario seleccionado ya fue reservado por otro usuario. Seleccione otro horario.",
    "details": { "horario_id": 10 }
  }
}
```

### `GET /citas` — Listar citas
**Acceso:** Paciente (sus citas), Médico (todas)  
**Query Params:** `?estado=programada&fecha_desde=2026-05-01&fecha_hasta=2026-05-31`

### `PUT /citas/:id` — Modificar cita
**Acceso:** Paciente (su cita), Médico (cualquiera)

### `DELETE /citas/:id` — Cancelar cita
**Acceso:** Paciente (su cita), Médico (cualquiera)  
> Genera notificación automática al paciente si la cancela el médico.

---

## 4.5 Servicios de Historial Clínico

### `POST /historial` — Registrar consulta
**Acceso:** Médico únicamente

**Request Body:**
```json
{
  "cita_id": 25,
  "signos_vitales": {
    "temperatura_corporal": 36.5,
    "peso_kg": 70.2,
    "altura_cm": 175,
    "presion_arterial": "120/80"
  },
  "diagnostico": "Cefalea tensional",
  "resultados_analisis": "Sin hallazgos relevantes",
  "prescripciones": "Paracetamol 500mg cada 8hrs por 5 días",
  "observaciones": "Paciente refiere estrés laboral"
}
```

> **Nota:** El servidor encripta todo el body con AES-256-GCM antes de almacenarlo. Se retorna al médico sin encriptar.

**Response (201):**
```json
{
  "success": true,
  "data": {
    "id": 12,
    "cita_id": 25,
    "paciente": "Juan Pérez García",
    "fecha_consulta": "2026-05-15T09:00:00Z"
  },
  "message": "Historial clínico registrado exitosamente"
}
```

### `GET /historial/paciente/:pacienteId` — Historial completo
**Acceso:** Médico, o el propio Paciente

**Response (200):**
```json
{
  "success": true,
  "data": {
    "paciente": {
      "nombre": "Juan Pérez García",
      "edad": 35,
      "sexo": "masculino",
      "correo_electronico": "juan@email.com"
    },
    "consultas": [
      {
        "id": 12,
        "fecha": "2026-05-15",
        "medico": "Dr. María López",
        "signos_vitales": {
          "temperatura_corporal": 36.5,
          "peso_kg": 70.2,
          "altura_cm": 175,
          "presion_arterial": "120/80"
        },
        "diagnostico": "Cefalea tensional",
        "resultados_analisis": "Sin hallazgos relevantes",
        "prescripciones": "Paracetamol 500mg cada 8hrs",
        "observaciones": "Paciente refiere estrés laboral"
      }
    ]
  }
}
```

---

## 4.6 Servicios de Notificaciones

### `GET /notificaciones` — Listar notificaciones del usuario
**Acceso:** Paciente, Médico (autenticado)  
**Query Params:** `?leida=false`

### `PATCH /notificaciones/:id/leer` — Marcar como leída
**Acceso:** El propio usuario

---

## 4.7 Servicios de Reportes

### `GET /reportes/pacientes` — Lista de pacientes
**Acceso:** Médico  
**Query Params:** `?formato=json` (default) o `?formato=pdf`

### `GET /reportes/calendario` — Calendario de citas
**Acceso:** Médico  
**Query Params:** `?mes=2026-05`

### `GET /reportes/historial/:pacienteId` — Historial clínico completo
**Acceso:** Médico, o el propio Paciente

**Response:**
```json
{
  "success": true,
  "data": {
    "encabezado": {
      "nombre": "Juan Pérez García",
      "edad": 35,
      "sexo": "masculino",
      "direccion": "Calle Reforma 123",
      "telefono": "5551234567",
      "correo_electronico": "juan@email.com"
    },
    "consultas": [
      {
        "fecha": "2026-05-15",
        "medico": "Dr. María López",
        "signos_vitales": { "...": "..." },
        "diagnostico": "...",
        "prescripciones": "..."
      }
    ]
  }
}
```

---

## 4.8 Resumen de Endpoints

| Método | Endpoint | Acceso | Descripción |
|--------|----------|--------|-------------|
| POST | `/auth/register` | Público | Registro de paciente |
| POST | `/auth/login` | Público | Inicio de sesión |
| GET | `/pacientes` | Médico | Listar pacientes |
| GET | `/pacientes/:id` | Médico/Paciente | Ver paciente |
| PUT | `/pacientes/:id` | Médico/Paciente | Actualizar paciente |
| DELETE | `/pacientes/:id` | Médico | Eliminar paciente |
| GET | `/horarios` | Autenticado | Horarios disponibles |
| POST | `/citas` | Autenticado | Crear cita (mutex) |
| GET | `/citas` | Autenticado | Listar citas |
| PUT | `/citas/:id` | Autenticado | Modificar cita |
| DELETE | `/citas/:id` | Autenticado | Cancelar cita |
| POST | `/historial` | Médico | Registrar consulta |
| GET | `/historial/paciente/:id` | Médico/Paciente | Ver historial |
| GET | `/notificaciones` | Autenticado | Ver notificaciones |
| PATCH | `/notificaciones/:id/leer` | Autenticado | Marcar leída |
| GET | `/reportes/pacientes` | Médico | Reporte pacientes |
| GET | `/reportes/calendario` | Médico | Reporte calendario |
| GET | `/reportes/historial/:id` | Médico/Paciente | Reporte historial |
