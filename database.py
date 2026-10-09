"""
=============================================================================
PROYECTO: EMPODER-ARTE
ARCHIVO: database.py
DESCRIPCIÓN: Capa de base de datos PostgreSQL (Supabase) para la plataforma
             Empoder-Arte. Gestiona dos tipos de usuarios (emprendedora /
             cliente), rastrea sus suscripciones (Gratuito / VIP) y controla
             el acceso al contenido VIP según el estado y la fecha de
             vencimiento del pago.

             Expone funciones auxiliares para:
               - Inicializar el esquema de la base de datos (14 tablas).
               - Registrar usuarios creando automáticamente su suscripción base.
               - Verificar credenciales de inicio de sesión.
               - Consultar el estado de suscripción por email o por id.
               - Actualizar el estado de suscripción (activar tras pago,
                 cortar acceso si está vencida, etc.).
               - Soporte para el panel de administración (listar y editar).
               - Reemplazo masivo de tablas tabulares desde un DataFrame.
               - CRUD de la tabla de anuncios (banner de publicidad).

             IMPLEMENTACIÓN:
               - psycopg2 (RealDictCursor) para DDL y escrituras parametrizadas.
               - SQLAlchemy (engine cacheado) sólo como conexión para pandas
                 (read_sql / to_sql) en el reemplazo de tablas.
=============================================================================
"""

import os
import hashlib
from datetime import datetime, date, timedelta

import psycopg2
import psycopg2.errors
from psycopg2.extras import RealDictCursor
from sqlalchemy import create_engine

# ---------------------------------------------------------
# CONFIGURACIÓN GENERAL
# ---------------------------------------------------------
# NOMBRE_DB se conserva (ya no se usa para conectar aquí, pero el script de
# migración lo necesita para localizar el SQLite origen).
NOMBRE_DB = "empoder_arte.db"

# Datos de la administradora / fundadora (único usuario inicial)
CORREO_ADMIN = "garcialarissa1292@gmail.com"
NOMBRE_ADMIN = "Larissa García (Fundadora)"

# Valor por defecto SOLO como fallback de compatibilidad (ver _resolver_admin_pass).
_ADMIN_PASS_DEFAULT = "Lariliz1*"


def _resolver_admin_pass():
    """Resuelve la contraseña de admin con la MISMA PRECEDENCIA que DB_URL:

      1) Variable de entorno ADMIN_PASS (script standalone / CI).
      2) st.secrets['ADMIN_PASS'] (cuando corre dentro de Streamlit).
      3) Parseo directo de .streamlit/secrets.toml con tomllib (stdlib 3.11+).

    Si no se encuentra en ninguna fuente, usa _ADMIN_PASS_DEFAULT como fallback
    de compatibilidad para que el login NO se rompa. El secret tiene prioridad.
    """
    # 1) Variable de entorno
    valor = os.environ.get("ADMIN_PASS")
    if valor:
        return valor

    # 2) Secrets de Streamlit (sólo disponible dentro de la app)
    try:
        import streamlit as st
        if "ADMIN_PASS" in st.secrets:
            return st.secrets["ADMIN_PASS"]
    except Exception:
        pass

    # 3) Parsear .streamlit/secrets.toml (hermano de este archivo)
    try:
        import tomllib
        ruta = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
        with open(ruta, "rb") as f:
            valor = tomllib.load(f).get("ADMIN_PASS")
            if valor:
                return valor
    except Exception:
        pass

    # 4) Fallback de compatibilidad
    return _ADMIN_PASS_DEFAULT


PASS_ADMIN_PLANA = _resolver_admin_pass()

# Valores válidos para los campos controlados
TIPOS_USUARIO = ("emprendedora", "cliente", "admin")
PLANES = ("Gratuito", "VIP")
ESTADOS_SUSCRIPCION = ("activo", "inactivo", "pendiente")

# Duración por defecto de una suscripción VIP (en días)
DIAS_VIGENCIA_VIP = 30


# ---------------------------------------------------------
# RESOLUCIÓN DE LA CADENA DE CONEXIÓN (DB_URL)
# ---------------------------------------------------------
def _resolver_db_url():
    """Resuelve la cadena de conexión a Postgres con PRECEDENCIA FIJA:

      1) Variable de entorno DB_URL (script standalone / CI).
      2) st.secrets['DB_URL'] (cuando corre dentro de Streamlit).
      3) Parseo directo de .streamlit/secrets.toml con tomllib (stdlib 3.11+).

    Devuelve la cadena o None si no se encontró en ninguna fuente.
    La contraseña NUNCA se hardcodea: siempre proviene de una de estas fuentes.
    """
    # 1) Variable de entorno
    url = os.environ.get("DB_URL")
    if url:
        return url

    # 2) Secrets de Streamlit (sólo disponible dentro de la app)
    try:
        import streamlit as st
        if "DB_URL" in st.secrets:
            return st.secrets["DB_URL"]
    except Exception:
        pass

    # 3) Último recurso: parsear .streamlit/secrets.toml (hermano de este archivo)
    try:
        import tomllib
        ruta = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
        with open(ruta, "rb") as f:
            return tomllib.load(f).get("DB_URL")
    except Exception:
        return None


def _forzar_driver_psycopg2(url):
    """Normaliza el prefijo de la URL a 'postgresql+psycopg2://' para que
    SQLAlchemy use psycopg2 (instalado) y NO intente psycopg (v3, ausente,
    que provoca ModuleNotFoundError: No module named 'psycopg')."""
    if not url:
        return url
    if url.startswith("postgresql+"):
        return url  # ya trae un driver explícito
    if url.startswith("postgresql://"):
        return "postgresql+psycopg2://" + url[len("postgresql://"):]
    if url.startswith("postgres://"):
        return "postgresql+psycopg2://" + url[len("postgres://"):]
    return url


# Se expone a nivel de módulo.
# URL para SQLAlchemy (engine): con driver psycopg2 forzado.
DB_URL = _forzar_driver_psycopg2(_resolver_db_url())
# URL "cruda" para psycopg2.connect() directo (obtener_conexion), sin el +psycopg2.
DB_URL_RAW = _resolver_db_url()


# ---------------------------------------------------------
# CONEXIÓN
# ---------------------------------------------------------
# Engine SQLAlchemy cacheado a nivel de módulo (lo usan las lecturas pandas y
# el reemplazo de tablas). Se crea una sola vez.
_ENGINE = None


def _get_engine():
    """Crea (una sola vez) y devuelve un engine de SQLAlchemy cacheado.
    Lo reutilizan las lecturas de pandas y reemplazar_tabla_desde_df."""
    global _ENGINE
    if _ENGINE is None:
        if not DB_URL:
            raise ConnectionError(
                "No se encontró la cadena de conexión a la base de datos (DB_URL). "
                "Configura DB_URL en los secretos de la aplicación."
            )
        _ENGINE = create_engine(DB_URL, pool_pre_ping=True)
    return _ENGINE


def obtener_conexion():
    """Devuelve una conexión psycopg2 a Postgres con filas tipo dict
    (RealDictCursor). Si DB_URL no está definido o la conexión falla, lanza
    ConnectionError con un mensaje legible (sin stack trace crudo)."""
    if not DB_URL_RAW:
        raise ConnectionError(
            "No se encontró la cadena de conexión a la base de datos (DB_URL). "
            "Configura DB_URL en los secretos de la aplicación."
        )
    try:
        # psycopg2.connect NO entiende el prefijo '+psycopg2'; usa la URL cruda.
        return psycopg2.connect(DB_URL_RAW, cursor_factory=RealDictCursor)
    except psycopg2.Error as exc:
        raise ConnectionError(
            "No fue posible conectar con la base de datos. "
            "Verifica tu conexión e inténtalo de nuevo."
        ) from exc


# ---------------------------------------------------------
# UTILIDADES DE SEGURIDAD
# ---------------------------------------------------------
def generar_hash(password: str) -> str:
    """Genera un hash SHA-256 de la contraseña para almacenarla de forma segura."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


# ---------------------------------------------------------
# INICIALIZACIÓN DEL ESQUEMA (14 TABLAS, DDL IDEMPOTENTE Y TRANSACCIONAL)
# ---------------------------------------------------------
# Cada sentencia es CREATE TABLE IF NOT EXISTS, por lo que es segura de
# re-ejecutar. Los identificadores con mayúscula (nombres reales del CSV) van
# entrecomillados con comillas dobles. Todo el DDL se emite en UNA sola
# transacción: un único commit al final o rollback + ConnectionError si falla.
_DDL_TABLAS = (
    # (1) usuarios --------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS usuarios (
        id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        nombre          TEXT NOT NULL,
        email           TEXT NOT NULL UNIQUE,
        password_hash   TEXT NOT NULL,
        tipo_usuario    TEXT NOT NULL CHECK (tipo_usuario IN ('emprendedora', 'cliente', 'admin')),
        fecha_registro  TEXT NOT NULL
    );
    """,
    # (2) suscripciones ---------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS suscripciones (
        id                 INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        usuario_id         INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
        plan               TEXT NOT NULL CHECK (plan IN ('Gratuito', 'VIP')),
        estado             TEXT NOT NULL CHECK (estado IN ('activo', 'inactivo', 'pendiente')),
        fecha_inicio       TEXT,
        fecha_vencimiento  TEXT
    );
    """,
    # (3) emprendedoras (22 columnas de datos con nombres reales) ---------
    """
    CREATE TABLE IF NOT EXISTS emprendedoras (
        id                   INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        "Email"              TEXT UNIQUE,
        "Nombre"             TEXT,
        "Negocio"            TEXT,
        "Tipo_Oferta"        TEXT,
        "Categoria"          TEXT,
        "WhatsApp"           TEXT,
        "Descripcion"        TEXT,
        "Estado_Pago"        TEXT,
        "Metodo_Pago"        TEXT,
        "Contacto"           TEXT,
        "Estado_Aprobacion"  TEXT,
        "Estado"             TEXT,
        "Ciudad"             TEXT,
        "Colonia"            TEXT,
        "lat"                TEXT,
        "lon"                TEXT,
        "Celular"            TEXT,
        "INE_Doc"            TEXT,
        "CURP_Doc"           TEXT,
        "Historia"           TEXT,
        "CURP_Valor"         TEXT,
        "Foto_Perfil"        TEXT
    );
    """,
    'CREATE UNIQUE INDEX IF NOT EXISTS ux_emprendedoras_email ON emprendedoras ("Email");',
    # (4) productos -------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS productos (
        id                   INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        "Email_Emprendedora" TEXT,
        "Producto"           TEXT,
        "Precio"             NUMERIC,
        "Categoria"          TEXT,
        "Stock"              TEXT,
        "Estado_Aprobacion"  TEXT,
        "Estado"             TEXT,
        "Foto_Producto"      TEXT
    );
    """,
    # (5) finanzas --------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS finanzas (
        id                   INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        "Fecha"              TEXT,
        "Email_Emprendedora" TEXT,
        "Cliente"            TEXT,
        "Concepto"           TEXT,
        "Monto"              NUMERIC,
        "Tipo"               TEXT
    );
    """,
    # (6) agenda ----------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS agenda (
        id                   INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        "Email_Emprendedora" TEXT,
        "Fecha"              TEXT,
        "Hora"               TEXT,
        "Evento"             TEXT,
        "Cliente_Contacto"   TEXT,
        "Notas"              TEXT
    );
    """,
    # (7) tareas ----------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS tareas (
        id                   INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        "Email_Emprendedora" TEXT,
        "Tarea"              TEXT,
        "Prioridad"          TEXT,
        "Estatus"            TEXT
    );
    """,
    # (8) evaluaciones ----------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS evaluaciones (
        id              INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        "Fecha"         TEXT,
        "Email_Destino" TEXT,
        "Autor_Email"   TEXT,
        "Autor_Nombre"  TEXT,
        "Calificacion"  TEXT,
        "Comentario"    TEXT
    );
    """,
    # (9) oraciones -------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS oraciones (
        id          INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        "Fecha"     TEXT,
        "Nombre"    TEXT,
        "Email"     TEXT,
        "Celular"   TEXT,
        "Area"      TEXT,
        "Peticion"  TEXT,
        "Privada"   TEXT
    );
    """,
    # (10) lives_grabados -------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS lives_grabados (
        id                    INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        "Fecha_Emision"       TEXT,
        "Email_Emprendedora"  TEXT,
        "Nombre_Emprendedora" TEXT,
        "Titulo_Live"         TEXT,
        "Frame_B64"           TEXT
    );
    """,
    # (11) chat_live ------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS chat_live (
        id         INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        "Hora"     TEXT,
        "Usuario"  TEXT,
        "Mensaje"  TEXT
    );
    """,
    # (12) publicaciones_muro --------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS publicaciones_muro (
        id        INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        "Email"   TEXT,
        "Nombre"  TEXT,
        "Fecha"   TEXT,
        "Texto"   TEXT
    );
    """,
    # (13) clientes -------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS clientes (
        id                   INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        "Email_Emprendedora" TEXT,
        "Nombre_Cliente"     TEXT,
        "Telefono"           TEXT,
        "Notas"              TEXT
    );
    """,
    # (14) anuncios (banner de publicidad) --------------------------------
    """
    CREATE TABLE IF NOT EXISTS anuncios (
        id             INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        titulo         TEXT,
        tipo           TEXT CHECK (tipo IN ('imagen', 'video')),
        contenido      TEXT,
        fecha_inicio   DATE,
        fecha_fin      DATE,
        activo         BOOLEAN DEFAULT true,
        fecha_creacion TEXT,
        precio         NUMERIC DEFAULT 59,
        anunciante     TEXT
    );
    """,
)


def inicializar_db():
    """Crea las 14 tablas si no existen (DDL idempotente) dentro de UNA sola
    transacción, y asegura que la administradora fundadora quede registrada
    con suscripción VIP activa.

    Si cualquier sentencia DDL falla, se hace rollback y se re-lanza como
    ConnectionError para que la capa de la app muestre un error claro."""
    conn = obtener_conexion()
    try:
        conn.autocommit = False
        cur = conn.cursor()
        for ddl in _DDL_TABLAS:
            cur.execute(ddl)
        conn.commit()
    except Exception as exc:
        conn.rollback()
        raise ConnectionError(
            "No fue posible inicializar la base de datos. "
            "Verifica tu conexión e inténtalo de nuevo."
        ) from exc
    finally:
        conn.close()

    # Asegura la cuenta de la fundadora como admin con VIP activo (gestiona su
    # propia transacción; corre después del commit del DDL).
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
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (nombre, email, generar_hash(password), tipo_usuario, fecha_registro),
        )
        usuario_id = cur.fetchone()["id"]

        # Fechas de la suscripción base.
        fecha_inicio = date.today().strftime("%Y-%m-%d")
        if plan == "VIP":
            fecha_vencimiento = (date.today() + timedelta(days=dias_vigencia)).strftime("%Y-%m-%d")
        else:
            fecha_vencimiento = None  # Gratuito no caduca.

        cur.execute(
            """
            INSERT INTO suscripciones (usuario_id, plan, estado, fecha_inicio, fecha_vencimiento)
            VALUES (%s, %s, %s, %s, %s);
            """,
            (usuario_id, plan, estado, fecha_inicio, fecha_vencimiento),
        )

        conn.commit()
        return {"ok": True, "mensaje": "Usuario registrado correctamente.", "usuario_id": usuario_id}

    except psycopg2.errors.UniqueViolation:
        conn.rollback()
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
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM usuarios WHERE email = %s;", (email,))
        fila = cur.fetchone()
    finally:
        conn.close()
    return dict(fila) if fila else None


def obtener_usuario_por_id(usuario_id: int):
    """Devuelve el registro del usuario (dict) por id, o None si no existe."""
    conn = obtener_conexion()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM usuarios WHERE id = %s;", (usuario_id,))
        fila = cur.fetchone()
    finally:
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
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT * FROM suscripciones
            WHERE usuario_id = %s
            ORDER BY id DESC
            LIMIT 1;
            """,
            (usuario_id,),
        )
        fila = cur.fetchone()
    finally:
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
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE suscripciones SET estado = %s WHERE id = %s;",
            (nuevo_estado, suscripcion["id"]),
        )
        conn.commit()
    finally:
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
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE suscripciones
            SET plan = 'VIP', estado = 'activo', fecha_inicio = %s, fecha_vencimiento = %s
            WHERE id = %s;
            """,
            (fecha_inicio, fecha_vencimiento, suscripcion["id"]),
        )
        conn.commit()
    finally:
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
    try:
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
            consulta += " WHERE u.tipo_usuario = %s"
            parametros = (tipo_usuario,)
        consulta += " ORDER BY u.tipo_usuario, u.nombre;"

        cur.execute(consulta, parametros)
        filas = [dict(f) for f in cur.fetchall()]
    finally:
        conn.close()
    return filas


def eliminar_usuario(usuario_id: int) -> bool:
    """Elimina un usuario y, por la clave foránea en cascada, sus suscripciones."""
    conn = obtener_conexion()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM usuarios WHERE id = %s;", (usuario_id,))
        conn.commit()
        afectados = cur.rowcount
    finally:
        conn.close()
    return afectados > 0


# ---------------------------------------------------------
# REEMPLAZO MASIVO DE TABLAS TABULARES DESDE UN DATAFRAME
# ---------------------------------------------------------
# Conjunto cerrado de tablas escribibles por la app + sus columnas reales (sin
# la PK sustituta 'id'). Es la ÚNICA fuente de verdad de qué nombres de tabla
# son válidos y qué columnas acepta cada una (evita inyección de SQL).
_COLUMNAS_POR_TABLA = {
    "emprendedoras": ["Email", "Nombre", "Negocio", "Tipo_Oferta", "Categoria", "WhatsApp",
                      "Descripcion", "Estado_Pago", "Metodo_Pago", "Contacto", "Estado_Aprobacion",
                      "Estado", "Ciudad", "Colonia", "lat", "lon", "Celular", "INE_Doc", "CURP_Doc",
                      "Historia", "CURP_Valor", "Foto_Perfil"],
    "productos": ["Email_Emprendedora", "Producto", "Precio", "Categoria", "Stock",
                  "Estado_Aprobacion", "Estado", "Foto_Producto"],
    "finanzas": ["Fecha", "Email_Emprendedora", "Cliente", "Concepto", "Monto", "Tipo"],
    "agenda": ["Email_Emprendedora", "Fecha", "Hora", "Evento", "Cliente_Contacto", "Notas"],
    "tareas": ["Email_Emprendedora", "Tarea", "Prioridad", "Estatus"],
    "evaluaciones": ["Fecha", "Email_Destino", "Autor_Email", "Autor_Nombre", "Calificacion", "Comentario"],
    "oraciones": ["Fecha", "Nombre", "Email", "Celular", "Area", "Peticion", "Privada"],
    "lives_grabados": ["Fecha_Emision", "Email_Emprendedora", "Nombre_Emprendedora", "Titulo_Live", "Frame_B64"],
    "chat_live": ["Hora", "Usuario", "Mensaje"],
}


def reemplazar_tabla_desde_df(tabla: str, df) -> None:
    """Reemplaza TODO el contenido de 'tabla' con las filas de 'df'.

    Transaccional: TRUNCATE + append dentro de una sola transacción.
    'tabla' debe ser una clave de _COLUMNAS_POR_TABLA (conjunto cerrado); si no,
    lanza ValueError antes de tocar la BD (sin superficie de inyección SQL).
    El DataFrame se reindexa a exactamente las columnas reales de la tabla:
    columnas extra (p. ej. 'id', 'Fecha_Obj') se descartan y las ausentes se
    añaden como NULL.
    """
    if tabla not in _COLUMNAS_POR_TABLA:
        raise ValueError(f"Tabla no permitida para reemplazo: {tabla!r}")

    columnas = _COLUMNAS_POR_TABLA[tabla]
    df = df.copy()
    df = df.reindex(columns=columnas)

    eng = _get_engine()
    with eng.begin() as conn:  # BEGIN; ... COMMIT (o ROLLBACK si falla)
        # El nombre de tabla proviene de una clave validada del dict, no de
        # entrada externa: sin riesgo de inyección.
        conn.exec_driver_sql(f'TRUNCATE TABLE {tabla} RESTART IDENTITY')
        df.to_sql(tabla, conn, if_exists="append", index=False)


def eliminar_fila_por_id(tabla: str, fila_id) -> bool:
    """Elimina UNA fila de 'tabla' por su columna 'id' (PK sustituta de Postgres).

    Forma robusta de borrar un registro sin depender de índices de pandas ni de
    coincidencias por contenido. 'tabla' debe ser una clave validada de
    _COLUMNAS_POR_TABLA (conjunto cerrado), así no hay superficie de inyección SQL.
    Devuelve True si se eliminó una fila.
    """
    if tabla not in _COLUMNAS_POR_TABLA:
        raise ValueError(f"Tabla no permitida para borrado: {tabla!r}")
    eng = _get_engine()
    with eng.begin() as conn:
        # El nombre de tabla sale de una clave validada; el id va parametrizado.
        res = conn.exec_driver_sql(f'DELETE FROM {tabla} WHERE id = %s', (int(fila_id),))
        return res.rowcount > 0


# ---------------------------------------------------------
# CRUD DE ANUNCIOS (BANNER DE PUBLICIDAD)
# ---------------------------------------------------------
# Columnas que pueden actualizarse de forma dinámica (conjunto cerrado para que
# actualizar_anuncio no permita inyección por nombres de columna arbitrarios).
_COLUMNAS_ANUNCIO = (
    "titulo", "tipo", "contenido", "fecha_inicio", "fecha_fin",
    "activo", "precio", "anunciante",
)


def crear_anuncio(titulo, tipo, contenido, fecha_inicio, fecha_fin,
                  anunciante="", precio=59, activo=True):
    """Inserta un anuncio nuevo y devuelve su id.
    'fecha_creacion' se fija con la hora actual (string)."""
    fecha_creacion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = obtener_conexion()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO anuncios
                (titulo, tipo, contenido, fecha_inicio, fecha_fin,
                 activo, fecha_creacion, precio, anunciante)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (titulo, tipo, contenido, fecha_inicio, fecha_fin,
             activo, fecha_creacion, precio, anunciante),
        )
        nuevo_id = cur.fetchone()["id"]
        conn.commit()
    finally:
        conn.close()
    return nuevo_id


def listar_anuncios() -> list:
    """Devuelve todos los anuncios como lista de dicts, del más reciente al más antiguo."""
    conn = obtener_conexion()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM anuncios ORDER BY id DESC;")
        filas = [dict(f) for f in cur.fetchall()]
    finally:
        conn.close()
    return filas


def obtener_anuncios_vigentes(fecha=None) -> list:
    """Devuelve los anuncios activos cuya ventana [fecha_inicio, fecha_fin]
    contiene 'fecha' (por defecto, hoy). Lista de dicts ordenada por id."""
    if fecha is None:
        fecha = date.today()
    conn = obtener_conexion()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT * FROM anuncios
            WHERE fecha_inicio <= %s AND fecha_fin >= %s AND activo = true
            ORDER BY id;
            """,
            (fecha, fecha),
        )
        filas = [dict(f) for f in cur.fetchall()]
    finally:
        conn.close()
    return filas


def actualizar_anuncio(id, **campos) -> bool:
    """Actualiza dinámicamente los campos indicados de un anuncio.
    Solo se aceptan columnas del conjunto cerrado _COLUMNAS_ANUNCIO (sin
    inyección por nombres de columna). Devuelve True si se actualizó una fila."""
    campos_validos = {k: v for k, v in campos.items() if k in _COLUMNAS_ANUNCIO}
    if not campos_validos:
        return False

    asignaciones = ", ".join(f"{col} = %s" for col in campos_validos)
    valores = list(campos_validos.values())
    valores.append(id)

    conn = obtener_conexion()
    try:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE anuncios SET {asignaciones} WHERE id = %s;",
            valores,
        )
        conn.commit()
        afectados = cur.rowcount
    finally:
        conn.close()
    return afectados > 0


def eliminar_anuncio(id) -> bool:
    """Elimina un anuncio por id. Devuelve True si se borró una fila."""
    conn = obtener_conexion()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM anuncios WHERE id = %s;", (id,))
        conn.commit()
        afectados = cur.rowcount
    finally:
        conn.close()
    return afectados > 0


def activar_desactivar_anuncio(id, activo) -> bool:
    """Activa o desactiva un anuncio. Devuelve True si se actualizó una fila."""
    conn = obtener_conexion()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE anuncios SET activo = %s WHERE id = %s;", (activo, id))
        conn.commit()
        afectados = cur.rowcount
    finally:
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
