"""
=============================================================================
PROYECTO: EMPODER-ARTE
ARCHIVO: database.py
DESCRIPCIÓN: Capa de base de datos SQLite para la plataforma Empoder-Arte.
             Gestiona dos tipos de usuarios (emprendedora / cliente), rastrea
             sus suscripciones (Gratuito / VIP) y controla el acceso al
             contenido VIP según el estado y la fecha de vencimiento del pago.

             Expone funciones auxiliares para:
               - Inicializar el esquema de la base de datos.
               - Registrar usuarios creando automáticamente su suscripción base.
               - Verificar credenciales de inicio de sesión.
               - Consultar el estado de suscripción por email o por id.
               - Actualizar el estado de suscripción (activar tras pago,
                 cortar acceso si está vencida, etc.).
               - Soporte para el panel de administración (listar y editar).
=============================================================================
"""

import os
import sqlite3
import hashlib
from datetime import datetime, date, timedelta

# ---------------------------------------------------------
# CONFIGURACIÓN GENERAL
# ---------------------------------------------------------
NOMBRE_DB = "empoder_arte.db"

# Datos de la administradora / fundadora (único usuario inicial)
CORREO_ADMIN = "garcialarissa1292@gmail.com"
NOMBRE_ADMIN = "Larissa García (Fundadora)"
PASS_ADMIN_PLANA = "Lariliz1*"

# Valores válidos para los campos controlados
TIPOS_USUARIO = ("emprendedora", "cliente", "admin")
PLANES = ("Gratuito", "VIP")
ESTADOS_SUSCRIPCION = ("activo", "inactivo", "pendiente")

# Duración por defecto de una suscripción VIP (en días)
DIAS_VIGENCIA_VIP = 30


# ---------------------------------------------------------
# CONEXIÓN
# ---------------------------------------------------------
def obtener_conexion() -> sqlite3.Connection:
    """Devuelve una conexión a SQLite con claves foráneas activadas y
    acceso a las filas por nombre de columna (sqlite3.Row)."""
    conn = sqlite3.connect(NOMBRE_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


# ---------------------------------------------------------
# UTILIDADES DE SEGURIDAD
# ---------------------------------------------------------
def generar_hash(password: str) -> str:
    """Genera un hash SHA-256 de la contraseña para almacenarla de forma segura."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


# ---------------------------------------------------------
# INICIALIZACIÓN DEL ESQUEMA
# ---------------------------------------------------------
def inicializar_db():
    """Crea las tablas 'usuarios' y 'suscripciones' si no existen y asegura
    que la administradora fundadora quede registrada con suscripción VIP activa."""
    conn = obtener_conexion()
    cur = conn.cursor()

    # --- Tabla de usuarios ---
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS usuarios (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre          TEXT    NOT NULL,
            email           TEXT    NOT NULL UNIQUE,
            password_hash   TEXT    NOT NULL,
            tipo_usuario    TEXT    NOT NULL CHECK (tipo_usuario IN ('emprendedora', 'cliente', 'admin')),
            fecha_registro  TEXT    NOT NULL
        );
        """
    )

    # --- Tabla de suscripciones (1 usuario -> N suscripciones; la vigente es la última) ---
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS suscripciones (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id         INTEGER NOT NULL,
            plan               TEXT    NOT NULL CHECK (plan IN ('Gratuito', 'VIP')),
            estado             TEXT    NOT NULL CHECK (estado IN ('activo', 'inactivo', 'pendiente')),
            fecha_inicio       TEXT,
            fecha_vencimiento  TEXT,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE
        );
        """
    )

    conn.commit()
    conn.close()

    # Asegura la cuenta de la fundadora como admin con VIP activo.
    _asegurar_admin()


def _asegurar_admin():
    """Crea (o reactiva) a la administradora fundadora con un VIP activo de larga vigencia."""
    if obtener_usuario_por_email(CORREO_ADMIN) is None:
        registrar_usuario(
            nombre=NOMBRE_ADMIN,
            email=CORREO_ADMIN,
            password=PASS_ADMIN_PLANA,
            tipo_usuario="admin",
            plan="VIP",
            estado="activo",
            dias_vigencia=3650,  # ~10 años para la fundadora
        )


# ---------------------------------------------------------
# REGISTRO DE USUARIOS (+ SUSCRIPCIÓN BASE AUTOMÁTICA)
# ---------------------------------------------------------
def registrar_usuario(
    nombre: str,
    email: str,
    password: str,
    tipo_usuario: str = "cliente",
    plan: str = "Gratuito",
    estado: str = None,
    dias_vigencia: int = DIAS_VIGENCIA_VIP,
) -> dict:
    """Registra un usuario y crea automáticamente su suscripción base.

    Reglas de la suscripción base:
      - Plan 'Gratuito'  -> estado 'activo' sin fecha de vencimiento.
      - Plan 'VIP'       -> estado 'activo' con vencimiento a 'dias_vigencia'.
      El parámetro 'estado' permite forzar un valor (p. ej. 'pendiente' si aún
      no se confirma el pago de un VIP).

    Devuelve: {"ok": bool, "mensaje": str, "usuario_id": int | None}
    """
    email = (email or "").strip().lower()
    nombre = (nombre or "").strip()

    if not nombre or not email or not password:
        return {"ok": False, "mensaje": "Nombre, email y contraseña son obligatorios.", "usuario_id": None}

    if tipo_usuario not in TIPOS_USUARIO:
        tipo_usuario = "cliente"
    if plan not in PLANES:
        plan = "Gratuito"

    # Estado por defecto según el plan.
    if estado is None:
        estado = "activo"
    if estado not in ESTADOS_SUSCRIPCION:
        estado = "activo"

    conn = obtener_conexion()
    cur = conn.cursor()

    try:
        fecha_registro = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute(
            """
            INSERT INTO usuarios (nombre, email, password_hash, tipo_usuario, fecha_registro)
            VALUES (?, ?, ?, ?, ?);
            """,
            (nombre, email, generar_hash(password), tipo_usuario, fecha_registro),
        )
        usuario_id = cur.lastrowid

        # Fechas de la suscripción base.
        fecha_inicio = date.today().strftime("%Y-%m-%d")
        if plan == "VIP":
            fecha_vencimiento = (date.today() + timedelta(days=dias_vigencia)).strftime("%Y-%m-%d")
        else:
            fecha_vencimiento = None  # Gratuito no caduca.

        cur.execute(
            """
            INSERT INTO suscripciones (usuario_id, plan, estado, fecha_inicio, fecha_vencimiento)
            VALUES (?, ?, ?, ?, ?);
            """,
            (usuario_id, plan, estado, fecha_inicio, fecha_vencimiento),
        )

        conn.commit()
        return {"ok": True, "mensaje": "Usuario registrado correctamente.", "usuario_id": usuario_id}

    except sqlite3.IntegrityError:
        return {"ok": False, "mensaje": "Ya existe un usuario con ese correo electrónico.", "usuario_id": None}
    finally:
        conn.close()


# ---------------------------------------------------------
# CONSULTA DE USUARIOS
# ---------------------------------------------------------
def obtener_usuario_por_email(email: str):
    """Devuelve el registro del usuario (dict) o None si no existe."""
    email = (email or "").strip().lower()
    conn = obtener_conexion()
    cur = conn.cursor()
    cur.execute("SELECT * FROM usuarios WHERE email = ?;", (email,))
    fila = cur.fetchone()
    conn.close()
    return dict(fila) if fila else None


def obtener_usuario_por_id(usuario_id: int):
    """Devuelve el registro del usuario (dict) por id, o None si no existe."""
    conn = obtener_conexion()
    cur = conn.cursor()
    cur.execute("SELECT * FROM usuarios WHERE id = ?;", (usuario_id,))
    fila = cur.fetchone()
    conn.close()
    return dict(fila) if fila else None


# ---------------------------------------------------------
# VERIFICACIÓN DE CREDENCIALES (LOGIN)
# ---------------------------------------------------------
def verificar_credenciales(email: str, password: str):
    """Verifica email + contraseña.

    Devuelve el dict del usuario (incluye su suscripción vigente bajo la clave
    'suscripcion') si las credenciales son correctas; None en caso contrario.
    """
    usuario = obtener_usuario_por_email(email)
    if not usuario:
        return None

    if usuario["password_hash"] != generar_hash(password):
        return None

    # Antes de devolverlo, sincroniza el estado por si la suscripción venció.
    verificar_y_actualizar_vencimiento(usuario["id"])
    usuario["suscripcion"] = obtener_suscripcion_por_id(usuario["id"])
    return usuario


# ---------------------------------------------------------
# CONSULTA Y GESTIÓN DE SUSCRIPCIONES
# ---------------------------------------------------------
def obtener_suscripcion_por_id(usuario_id: int):
    """Devuelve la suscripción más reciente de un usuario (dict) o None."""
    conn = obtener_conexion()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM suscripciones
        WHERE usuario_id = ?
        ORDER BY id DESC
        LIMIT 1;
        """,
        (usuario_id,),
    )
    fila = cur.fetchone()
    conn.close()
    return dict(fila) if fila else None


def obtener_suscripcion_por_email(email: str):
    """Devuelve la suscripción vigente de un usuario a partir de su email."""
    usuario = obtener_usuario_por_email(email)
    if not usuario:
        return None
    return obtener_suscripcion_por_id(usuario["id"])


def _esta_vencida(suscripcion: dict) -> bool:
    """True si la suscripción tiene fecha de vencimiento y ya pasó."""
    venc = suscripcion.get("fecha_vencimiento") if suscripcion else None
    if not venc:
        return False
    try:
        fecha_venc = datetime.strptime(venc, "%Y-%m-%d").date()
        return date.today() > fecha_venc
    except (ValueError, TypeError):
        return False


def verificar_y_actualizar_vencimiento(usuario_id: int):
    """Si la suscripción VIP del usuario venció, la marca como 'inactivo'.
    Devuelve la suscripción (posiblemente actualizada) o None."""
    suscripcion = obtener_suscripcion_por_id(usuario_id)
    if not suscripcion:
        return None

    if suscripcion["estado"] == "activo" and _esta_vencida(suscripcion):
        actualizar_estado_suscripcion(usuario_id, "inactivo")
        suscripcion = obtener_suscripcion_por_id(usuario_id)

    return suscripcion


def tiene_acceso_vip(email_o_id) -> bool:
    """True solo si el usuario tiene plan 'VIP', estado 'activo' y no está vencida.

    Acepta un email (str) o un usuario_id (int).
    """
    if isinstance(email_o_id, str):
        usuario = obtener_usuario_por_email(email_o_id)
        if not usuario:
            return False
        usuario_id = usuario["id"]
    else:
        usuario_id = email_o_id

    suscripcion = verificar_y_actualizar_vencimiento(usuario_id)
    if not suscripcion:
        return False

    return (
        suscripcion["plan"] == "VIP"
        and suscripcion["estado"] == "activo"
        and not _esta_vencida(suscripcion)
    )


def actualizar_estado_suscripcion(usuario_id: int, nuevo_estado: str) -> bool:
    """Actualiza únicamente el estado ('activo' / 'inactivo' / 'pendiente')
    de la suscripción vigente del usuario."""
    if nuevo_estado not in ESTADOS_SUSCRIPCION:
        return False

    suscripcion = obtener_suscripcion_por_id(usuario_id)
    if not suscripcion:
        return False

    conn = obtener_conexion()
    cur = conn.cursor()
    cur.execute(
        "UPDATE suscripciones SET estado = ? WHERE id = ?;",
        (nuevo_estado, suscripcion["id"]),
    )
    conn.commit()
    conn.close()
    return True


def activar_suscripcion_vip(usuario_id: int, dias_vigencia: int = DIAS_VIGENCIA_VIP) -> bool:
    """Activa (o renueva) una suscripción VIP tras confirmarse el pago:
    cambia el plan a 'VIP', estado 'activo' y fija una nueva fecha de vencimiento."""
    suscripcion = obtener_suscripcion_por_id(usuario_id)
    if not suscripcion:
        return False

    fecha_inicio = date.today().strftime("%Y-%m-%d")
    fecha_vencimiento = (date.today() + timedelta(days=dias_vigencia)).strftime("%Y-%m-%d")

    conn = obtener_conexion()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE suscripciones
        SET plan = 'VIP', estado = 'activo', fecha_inicio = ?, fecha_vencimiento = ?
        WHERE id = ?;
        """,
        (fecha_inicio, fecha_vencimiento, suscripcion["id"]),
    )
    conn.commit()
    conn.close()
    return True


# ---------------------------------------------------------
# SOPORTE PARA EL PANEL DE ADMINISTRACIÓN
# ---------------------------------------------------------
def listar_usuarios_con_suscripcion(tipo_usuario: str = None) -> list:
    """Devuelve una lista de dicts con los datos del usuario y su suscripción
    vigente (plan, estado, vencimiento). Útil para el panel de administración.

    Si 'tipo_usuario' se indica ('emprendedora' / 'cliente' / 'admin'),
    filtra solo ese tipo.
    """
    conn = obtener_conexion()
    cur = conn.cursor()

    consulta = """
        SELECT
            u.id            AS usuario_id,
            u.nombre        AS nombre,
            u.email         AS email,
            u.tipo_usuario  AS tipo_usuario,
            u.fecha_registro AS fecha_registro,
            s.plan          AS plan,
            s.estado        AS estado,
            s.fecha_inicio  AS fecha_inicio,
            s.fecha_vencimiento AS fecha_vencimiento
        FROM usuarios u
        LEFT JOIN suscripciones s
            ON s.id = (
                SELECT id FROM suscripciones
                WHERE usuario_id = u.id
                ORDER BY id DESC LIMIT 1
            )
    """
    parametros = ()
    if tipo_usuario in TIPOS_USUARIO:
        consulta += " WHERE u.tipo_usuario = ?"
        parametros = (tipo_usuario,)
    consulta += " ORDER BY u.tipo_usuario, u.nombre;"

    cur.execute(consulta, parametros)
    filas = [dict(f) for f in cur.fetchall()]
    conn.close()
    return filas


def eliminar_usuario(usuario_id: int) -> bool:
    """Elimina un usuario y, por la clave foránea en cascada, sus suscripciones."""
    conn = obtener_conexion()
    cur = conn.cursor()
    cur.execute("DELETE FROM usuarios WHERE id = ?;", (usuario_id,))
    conn.commit()
    afectados = cur.rowcount
    conn.close()
    return afectados > 0


# ---------------------------------------------------------
# EJECUCIÓN DIRECTA: inicializa la base de datos.
# ---------------------------------------------------------
if __name__ == "__main__":
    inicializar_db()
    print(f"Base de datos '{NOMBRE_DB}' inicializada correctamente.")
    print("Usuarios registrados:")
    for u in listar_usuarios_con_suscripcion():
        print(f"  - [{u['tipo_usuario']}] {u['nombre']} <{u['email']}> "
              f"| Plan: {u['plan']} | Estado: {u['estado']} | Vence: {u['fecha_vencimiento']}")
