# 6. Mecanismos de Seguridad

## 6.1 Visión General de Seguridad

```
┌─────────────────────────────────────────────────────────┐
│                  CAPAS DE SEGURIDAD                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. TRANSPORTE ─── HTTPS / TLS 1.3                     │
│       ↓                                                 │
│  2. AUTENTICACIÓN ─── JWT (HS256, exp: 24h)            │
│       ↓                                                 │
│  3. AUTORIZACIÓN ─── RBAC (paciente / médico)          │
│       ↓                                                 │
│  4. VALIDACIÓN ─── Pydantic v2 (automática)            │
│       ↓                                                 │
│  5. ENCRIPTACIÓN EN REPOSO ─── AES-256-GCM             │
│       ↓                                                 │
│  6. HASHING ─── passlib[bcrypt] (12 salt rounds)       │
│       ↓                                                 │
│  7. PROTECCIÓN API ─── SlowAPI, CORSMiddleware         │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 6.2 Autenticación — JWT (JSON Web Tokens)

### Flujo de Autenticación

```
Usuario                    API Server (FastAPI)          Base de Datos
   │                          │                              │
   ├── POST /auth/login ─────►│                              │
   │   {user, password}       │                              │
   │                          ├── SELECT usuario ───────────►│
   │                          │◄── {id, password_hash} ──────┤
   │                          │                              │
   │                          ├── passlib.verify(            │
   │                          │     password, hash) ── OK    │
   │                          │                              │
   │                          ├── jose.jwt.encode({          │
   │                          │     sub: id,                 │
   │                          │     rol: 'paciente',         │
   │                          │     exp: 24h                 │
   │                          │   }, SECRET_KEY)             │
   │                          │                              │
   │◄── {token: "eyJ..."} ───┤                              │
   │                          │                              │
   ├── GET /citas ────────────►                              │
   │   Authorization:          │                              │
   │   Bearer eyJ...           ├── jwt.decode(token) ── OK  │
   │                          ├── Ejecutar lógica ──────────►│
   │◄── {data: [...]} ────────┤◄── resultados ──────────────┤
```

### Configuración JWT

| Parámetro | Valor |
|-----------|-------|
| Algoritmo | HS256 (HMAC-SHA256) |
| Expiración | 24 horas |
| Secret | Variable de entorno `JWT_SECRET` (256 bits mínimo) |
| Payload | `sub` (user id), `username`, `rol`, `iat`, `exp` |
| Librería | python-jose[cryptography] |

### Dependencia de Autenticación (FastAPI)

```python
from datetime import datetime, timedelta
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

class TokenData(BaseModel):
    sub: int
    username: str
    rol: str

SECRET_KEY = os.environ["JWT_SECRET"]
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24


def crear_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def obtener_usuario_actual(
    token: str = Depends(oauth2_scheme),
) -> TokenData:
    """Dependencia de FastAPI que verifica el JWT en cada request protegido."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return TokenData(
            sub=payload["sub"],
            username=payload["username"],
            rol=payload["rol"],
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "TOKEN_INVALID", "message": "Token inválido o expirado"},
            headers={"WWW-Authenticate": "Bearer"},
        )
```

---

## 6.3 Autorización — RBAC (Role-Based Access Control)

### Matriz de Permisos

| Recurso / Acción | Paciente | Médico |
|-------------------|----------|--------|
| Registrarse | ✅ | ❌ (pre-registro) |
| Ver perfil propio | ✅ | ✅ |
| Editar perfil propio | ✅ | ✅ |
| Listar todos los pacientes | ❌ | ✅ |
| Eliminar paciente | ❌ | ✅ |
| Ver horarios disponibles | ✅ | ✅ |
| Crear cita (propia) | ✅ | ✅ |
| Crear cita (para otro) | ❌ | ✅ |
| Ver citas propias | ✅ | ✅ (todas) |
| Cancelar cita propia | ✅ | ✅ (cualquiera) |
| Registrar historial clínico | ❌ | ✅ |
| Ver historial propio | ✅ | ✅ (cualquiera) |
| Reportes de pacientes | ❌ | ✅ |
| Reportes de calendario | ❌ | ✅ |

### Dependencia de Autorización (FastAPI)

```python
from functools import wraps
from fastapi import Depends, HTTPException, status


class RoleChecker:
    """Dependencia reutilizable para verificar roles."""

    def __init__(self, roles_permitidos: list[str]):
        self.roles_permitidos = roles_permitidos

    def __call__(self, usuario: TokenData = Depends(obtener_usuario_actual)):
        if usuario.rol not in self.roles_permitidos:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "No tiene permisos"},
            )
        return usuario


# Instancias reutilizables
solo_medico = RoleChecker(["medico"])
paciente_o_medico = RoleChecker(["paciente", "medico"])

# Uso en routers:
@router.get("/pacientes")
async def lista_pacientes(usuario: TokenData = Depends(solo_medico)):
    ...

@router.post("/historial")
async def registrar_historial(usuario: TokenData = Depends(solo_medico)):
    ...

@router.get("/citas")
async def listar_citas(usuario: TokenData = Depends(paciente_o_medico)):
    ...
```

---

## 6.4 Hashing de Contraseñas — passlib[bcrypt]

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
BCRYPT_ROUNDS = 12  # Configurado en passlib por defecto


def hash_password(plain_password: str) -> str:
    """Hashea una contraseña con bcrypt + salt automático."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed: str) -> bool:
    """Compara contraseña en texto plano contra el hash almacenado."""
    return pwd_context.verify(plain_password, hashed)
```

**¿Por qué bcrypt con 12 rounds?**
- Resistente a ataques de fuerza bruta (≈250ms por hash)
- Salt incorporado automáticamente
- Factor de costo ajustable para hardware futuro

---

## 6.5 Encriptación de Historial Clínico — AES-256-GCM

Los datos del historial clínico son **información médica sensible** y deben almacenarse encriptados.

### Algoritmo: AES-256-GCM (Galois/Counter Mode)
- **Confidencialidad**: Cifrado simétrico de 256 bits
- **Integridad**: Tag de autenticación GCM (evita manipulación)
- **Único por registro**: IV (vector de inicialización) aleatorio por cada registro

```python
import os
import json
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Clave de 32 bytes (256 bits) desde variable de entorno
ENCRYPTION_KEY = bytes.fromhex(os.environ["ENCRYPTION_KEY"])


def encriptar_datos(datos: dict) -> tuple[bytes, bytes]:
    """
    Encripta un diccionario JSON con AES-256-GCM.
    Retorna (datos_encriptados, iv).
    El auth_tag se concatena automáticamente al final del ciphertext por AESGCM.
    """
    aesgcm = AESGCM(ENCRYPTION_KEY)
    iv = os.urandom(12)  # 96 bits, recomendado para GCM
    json_bytes = json.dumps(datos, ensure_ascii=False).encode("utf-8")

    # AESGCM.encrypt() retorna ciphertext + auth_tag (16 bytes) concatenados
    datos_encriptados = aesgcm.encrypt(iv, json_bytes, None)

    return datos_encriptados, iv


def desencriptar_datos(datos_encriptados: bytes, iv: bytes) -> dict:
    """
    Desencripta datos con AES-256-GCM.
    Verifica integridad automáticamente (auth_tag incluido en el ciphertext).
    Lanza InvalidTag si los datos fueron manipulados.
    """
    aesgcm = AESGCM(ENCRYPTION_KEY)
    json_bytes = aesgcm.decrypt(iv, datos_encriptados, None)

    return json.loads(json_bytes.decode("utf-8"))
```

### Flujo de Encriptación/Desencriptación

```
ESCRITURA (POST /historial):
  dict datos ──► json.dumps ──► AES-256-GCM encrypt ──► BYTEA en DB
                                      │
                                 genera IV (almacenado junto al dato)

LECTURA (GET /historial):
  BYTEA en DB ──► AES-256-GCM decrypt (con IV) ──► json.loads ──► Response
```

---

## 6.6 Protección de la API

### Rate Limiting (SlowAPI)
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# Límite general: 100 requests por minuto por IP
@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    # Configurado globalmente en SlowAPI
    return await call_next(request)

# Límite de login: 5 intentos por 15 minutos (previene fuerza bruta)
@router.post("/auth/login")
@limiter.limit("5/15minutes")
async def login(request: Request, body: LoginSchema):
    ...
```

### CORS (CORSMiddleware de FastAPI)
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ["FRONTEND_URL"]],  # Solo el frontend autorizado
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)
```

### Validación de Entrada (Pydantic — automática)
```python
from pydantic import BaseModel, EmailStr, Field
from typing import Literal


class RegistroSchema(BaseModel):
    """Pydantic valida automáticamente cada campo al recibir el request."""

    username: str = Field(min_length=4, max_length=50, pattern=r"^[a-zA-Z0-9.]+$")
    password: str = Field(min_length=8)
    nombre: str = Field(min_length=2, max_length=150)
    direccion: str | None = None
    correo_electronico: EmailStr
    telefono: str | None = Field(default=None, max_length=20)
    edad: int = Field(gt=0, lt=150)
    sexo: Literal["masculino", "femenino", "otro"]


# FastAPI rechaza automáticamente datos inválidos con un 422 detallado.
# No se necesita código de validación manual.
@router.post("/auth/register", status_code=201)
async def register(body: RegistroSchema, db: AsyncSession = Depends(get_db)):
    ...  # body ya está validado por Pydantic
```

---

## 6.7 Variables de Entorno Sensibles

```env
# .env (NUNCA versionar en Git)
JWT_SECRET=a1b2c3d4e5f6...          # 256 bits mínimo, generado aleatoriamente
ENCRYPTION_KEY=f6e5d4c3b2a1...      # 32 bytes hex para AES-256
DATABASE_URL=postgresql+asyncpg://app_user:secure_password@localhost:5432/mediapp
FRONTEND_URL=https://mediapp.com
ENVIRONMENT=production
```

## 6.8 Resumen de Mecanismos de Seguridad

| Amenaza | Mecanismo de Defensa |
|---------|---------------------|
| Acceso no autorizado | JWT con expiración de 24h (python-jose) |
| Escalación de privilegios | RBAC con `Depends(RoleChecker)` |
| Robo de contraseñas | passlib[bcrypt] (12 rounds) — nunca texto plano |
| Exposición de datos médicos | AES-256-GCM con IV único (cryptography) |
| Fuerza bruta en login | SlowAPI rate limiting (5 intentos / 15 min) |
| Inyección SQL | SQLAlchemy ORM con consultas parametrizadas |
| XSS / clickjacking | Middleware de headers seguros + CSP |
| CSRF | CORSMiddleware restrictivo + tokens Bearer |
| Man-in-the-middle | HTTPS / TLS 1.3 |
| Datos sensibles en código | Variables de entorno (.env) + pydantic-settings |
