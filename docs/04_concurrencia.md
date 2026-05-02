# 5. Mecanismo de Control de Concurrencia

## 5.1 Problema de Concurrencia

En un sistema de citas médicas, múltiples pacientes pueden intentar reservar el **mismo horario** simultáneamente. Sin un mecanismo adecuado, se producirían:
- **Doble reserva** (two-write problem): Dos pacientes creen haber reservado el mismo slot.
- **Lecturas sucias**: Un paciente ve un horario como disponible mientras otro lo está reservando.
- **Condiciones de carrera**: El resultado depende del orden de ejecución no determinista.

## 5.2 Solución: Exclusión Mutua Distribuida con Bloqueo Optimista + Pesimista

Se implementa un modelo **híbrido** de dos niveles:

### Nivel 1 — Bloqueo Optimista (Application Layer)
Cada horario tiene un campo `version` que se incrementa con cada modificación. Al crear una cita:

1. El cliente obtiene el horario con su `version` actual.
2. Al enviar la reserva, incluye la `version` que leyó.
3. El servidor verifica que la `version` no haya cambiado antes de proceder.

### Nivel 2 — Bloqueo Pesimista (Database Layer)
Dentro de una transacción serializable, se usa `SELECT ... FOR UPDATE` para bloquear la fila del horario:

```
Patient A ──► SELECT FOR UPDATE (slot_id=10) ──► BLOQUEA FILA
Patient B ──► SELECT FOR UPDATE (slot_id=10) ──► ESPERA...
Patient A ──► UPDATE + INSERT ──► COMMIT ──► LIBERA
Patient B ──► FILA DESBLOQUEADA ──► Lee is_available=FALSE ──► ROLLBACK + Error 409
```

## 5.3 Pseudocódigo de la Transacción (Python + FastAPI + SQLAlchemy)

```python
from sqlalchemy import select, update, insert
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status


async def create_appointment(
    patient_id: int,
    slot_id: int,
    client_version: int,
    reason: str,
    created_by: str,
    db: AsyncSession
) -> dict:
    """
    Crea una cita médica con exclusión mutua distribuida.
    Usa bloqueo optimista (version) + pesimista (SELECT FOR UPDATE).
    """
    try:
        # 1. Iniciar transacción con nivel de aislamiento SERIALIZABLE
        #    (configurado en la sesión o por transacción)
        await db.execute(
            text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
        )

        # 2. Bloqueo pesimista: SELECT FOR UPDATE bloquea la fila
        #    Otros procesos que intenten leer esta fila quedarán en espera
        result = await db.execute(
            select(AvailableSlot)
            .where(AvailableSlot.id == slot_id)
            .with_for_update()  # ← EXCLUSIÓN MUTUA a nivel de fila
        )
        slot = result.scalar_one_or_none()

        # 3. Verificación de bloqueo optimista: ¿cambió la versión?
        if slot is None or slot.version != client_version:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "SLOT_VERSION_MISMATCH",
                    "message": "El horario fue modificado por otro usuario."
                }
            )

        # 4. Verificar disponibilidad
        if not slot.is_available:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "SLOT_NOT_AVAILABLE",
                    "message": "El horario ya fue reservado. Seleccione otro."
                }
            )

        # 5. Marcar horario como no disponible e incrementar versión
        slot.is_available = False
        slot.version += 1

        # 6. Crear la cita
        new_appointment = Appointment(
            patient_id=patient_id,
            doctor_id=slot.doctor_id,
            slot_id=slot_id,
            status="scheduled",
            created_by=created_by,
            reason=reason,
        )
        db.add(new_appointment)

        # 7. Confirmar transacción — LIBERA el bloqueo
        await db.commit()
        await db.refresh(new_appointment)

        return new_appointment

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()

        # Manejar error de serialización de PostgreSQL
        if hasattr(e, "orig") and getattr(e.orig, "sqlstate", None) == "40001":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "SERIALIZATION_FAILURE",
                    "message": "Conflicto de concurrencia. Intente nuevamente."
                }
            )
        raise
```

## 5.4 Diagrama de Secuencia — Escenario Concurrente

```
Patient A                    API Server (FastAPI)          PostgreSQL
    │                            │                            │
    ├── GET /slots ─────────────►│                            │
    │                            ├── SELECT available_slots ─►│
    │◄── {id:10, v:1, avail:T} ─┤◄── results ───────────────┤
    │                            │                            │
    ├── POST /appointments ─────►│                            │
    │   {slot_id:10, v:1}        ├── BEGIN ──────────────────►│
    │                            ├── SELECT..FOR UPDATE ─────►│
    │                            │   (LOCKS ROW 10)           │◄── row locked
    │                            │                            │
    │         Patient B          │                            │
    │             │               │                            │
    │             ├── POST /appointments──────────►│           │
    │             │  {slot_id:10, v:1}             │           │
    │             │               ├── BEGIN ──────────────────►│
    │             │               ├── SELECT..FOR UPDATE ─────►│
    │             │               │   (WAITS — row locked)     │
    │             │               │                ┆ BLOCKED  ┆│
    │                            │                            │
    │                            ├── is_available=TRUE? ── YES│
    │                            ├── UPDATE is_available=FALSE►│
    │                            ├── INSERT INTO appointments►│
    │                            ├── COMMIT ─────────────────►│
    │                            │   (RELEASES LOCK)          │
    │◄── 201 Appointment created─┤                            │
    │                            │                            │
    │             │               │   (ROW UNLOCKED)          │
    │             │               │◄── is_available=FALSE ────┤
    │             │               ├── ROLLBACK ───────────────►│
    │             │◄── 409 Conflict ─────────────┤            │
    │             │  "Slot already booked"        │            │
```

## 5.5 Manejo de Cancelación y Liberación de Horario

Cuando se cancela una cita, se libera el horario dentro de una transacción:

```python
async def cancel_appointment(
    appointment_id: int,
    cancelled_by: str,
    db: AsyncSession
) -> None:
    """
    Cancela una cita y libera el horario correspondiente.
    Si cancela el médico, genera notificación al paciente.
    """
    try:
        # 1. Bloquear la cita con FOR UPDATE
        result = await db.execute(
            select(Appointment)
            .where(Appointment.id == appointment_id)
            .with_for_update()
        )
        appointment = result.scalar_one_or_none()

        if appointment is None:
            raise HTTPException(status_code=404, detail="Appointment not found")

        # 2. Actualizar estado de la cita
        appointment.status = "cancelled"

        # 3. Liberar el horario e incrementar versión
        slot_result = await db.execute(
            select(AvailableSlot)
            .where(AvailableSlot.id == appointment.slot_id)
            .with_for_update()
        )
        slot = slot_result.scalar_one()
        slot.is_available = True
        slot.version += 1

        # 4. Si canceló el médico, notificar al paciente
        if cancelled_by == "doctor":
            # Obtener user_id del paciente
            patient_result = await db.execute(
                select(Patient.user_id)
                .where(Patient.id == appointment.patient_id)
            )
            user_id = patient_result.scalar_one()

            notification = Notification(
                user_id=user_id,
                type="appointment_cancelled",
                message="Su cita ha sido cancelada por el médico.",
                reference={"type": "appointment", "id": appointment_id},
            )
            db.add(notification)

        # 5. Confirmar transacción
        await db.commit()

    except HTTPException:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        raise
```

## 5.6 Resumen de Garantías

| Propiedad | Mecanismo | Garantía |
|-----------|-----------|----------|
| **Exclusión mutua** | `SELECT ... FOR UPDATE` (`.with_for_update()` en SQLAlchemy) | Solo un proceso modifica un horario a la vez |
| **Detección de conflictos** | Campo `version` (optimista) | Detecta cambios entre lectura y escritura |
| **Atomicidad** | Transacciones PostgreSQL (`AsyncSession` con commit/rollback) | Todo se confirma o nada se confirma |
| **Aislamiento** | Nivel SERIALIZABLE | Las transacciones se ejecutan como si fueran secuenciales |
| **Deadlock prevention** | Orden consistente de bloqueos + timeout | PostgreSQL detecta y resuelve deadlocks automáticamente |
