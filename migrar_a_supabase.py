"""
=============================================================================
PROYECTO: EMPODER-ARTE
ARCHIVO: migrar_a_supabase.py
DESCRIPCIÓN: Script STANDALONE, idempotente y verificable que migra TODOS los
             datos reales de la app (auth en SQLite + CSV tabulares) a la base
             PostgreSQL gestionada por Supabase, SIN perder ningún dato ni
             registro.

             Se ejecuta UNA sola vez en la máquina local (la que tiene
             empoder_arte.db y .streamlit/secrets.toml); NO está pensado para
             correr en la nube ni en CI. Correrlo varias veces deja Postgres en
             el mismo estado (idempotencia por UPSERT / TRUNCATE+append).

             Verifica conteos de filas por tabla, agregados globales (14 tablas
             creadas, 6 filas de datos) Y valores concretos (suscripción admin,
             usuario admin, foto base64, Precio/Monto). Sólo imprime
             'MIGRACION OK' y sale con código 0 si todo coincide; ante cualquier
             discrepancia aborta con código de salida != 0.

             EJECUCIÓN (ruta completa obligatoria en Windows/PowerShell):
               & "$env:LOCALAPPDATA\\Programs\\Python\\Python314\\python.exe" migrar_a_supabase.py

             La contraseña de conexión NUNCA se hardcodea: DB_URL se resuelve
             con la misma precedencia fija que database.py.
=============================================================================
"""

import os
import sys
import hashlib
import sqlite3

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

import database


# ---------------------------------------------------------
# Rutas de origen (hermanas de este script, en la raíz del repo)
# ---------------------------------------------------------
_RAIZ = os.path.dirname(os.path.abspath(__file__))
_SQLITE = os.path.join(_RAIZ, database.NOMBRE_DB)

# Mapa archivo CSV -> tabla Postgres (sólo las tablas con datos a migrar).
_CSV_EMPRENDEDORAS = os.path.join(_RAIZ, "emprendedoras.csv")
_CSV_PRODUCTOS = os.path.join(_RAIZ, "productos.csv")
_CSV_FINANZAS = os.path.join(_RAIZ, "finanzas.csv")

# Las 13 tablas de datos (sin 'anuncios') y su CSV de origen (None = SQLite/sin CSV).
_TABLAS_DATOS = [
    "usuarios", "suscripciones", "emprendedoras", "productos", "finanzas",
    "agenda", "tareas", "evaluaciones", "oraciones", "lives_grabados",
    "chat_live", "publicaciones_muro", "clientes",
]

# CSV de cada tabla por-CSV (para contar el origen). Las vacías existen igual.
_CSV_POR_TABLA = {
    "emprendedoras": "emprendedoras.csv",
    "productos": "productos.csv",
    "finanzas": "finanzas.csv",
    "agenda": "agenda.csv",
    "tareas": "tareas.csv",
    "evaluaciones": "evaluaciones.csv",
    "oraciones": "oraciones.csv",
    "lives_grabados": "lives_grabados.csv",
    "chat_live": "chat_live.csv",
    "publicaciones_muro": "publicaciones_muro.csv",
    "clientes": "clientes.csv",
}


def _abortar(mensaje: str, codigo: int = 1):
    """Imprime un mensaje de error y termina con código != 0."""
    print(f"ERROR: {mensaje}")
    sys.exit(codigo)


def _contar_origen_sqlite(cur_sqlite, tabla: str) -> int:
    cur_sqlite.execute(f"SELECT COUNT(*) FROM {tabla}")
    return cur_sqlite.fetchone()[0]


def _contar_origen_csv(tabla: str) -> int:
    nombre = _CSV_POR_TABLA.get(tabla)
    if not nombre:
        return 0
    ruta = os.path.join(_RAIZ, nombre)
    if not os.path.exists(ruta):
        return 0
    return len(pd.read_csv(ruta))


def _contar_postgres(cur_pg, tabla: str) -> int:
    cur_pg.execute(f"SELECT COUNT(*) FROM {tabla}")
    return cur_pg.fetchone()["count"]


# =========================================================================
# PASO 0 — Precondición: debe existir el SQLite origen junto al script.
# =========================================================================
def paso_0_precondicion():
    if not os.path.exists(_SQLITE):
        _abortar(
            f"No se encontró '{database.NOMBRE_DB}' junto al script. "
            "Este script se corre UNA sola vez en la máquina local que tiene el "
            "SQLite origen (no en la nube ni en CI)."
        )
    print(f"[0] Precondición OK: '{database.NOMBRE_DB}' presente.")


# =========================================================================
# PASO 1 — Resolver DB_URL (misma precedencia fija que database.py).
# =========================================================================
def paso_1_resolver_db_url():
    url = database._resolver_db_url()
    if not url:
        _abortar(
            "No se encontró la cadena de conexión DB_URL "
            "(ni en os.environ, ni en st.secrets, ni en .streamlit/secrets.toml)."
        )
    print("[1] DB_URL resuelta correctamente.")
    return url


# =========================================================================
# PASO 2 — Inicializar el esquema completo (14 tablas, idempotente).
# =========================================================================
def paso_2_inicializar():
    database.inicializar_db()
    print("[2] Esquema inicializado (14 tablas) y admin asegurada.")


# =========================================================================
# PASO 3 — Migrar usuarios y suscripciones desde SQLite preservando ids y
#          VALORES reales (UPSERT DO UPDATE, NO recomputar fechas con hoy).
# =========================================================================
def paso_3_migrar_auth(conn_pg):
    sq = sqlite3.connect(_SQLITE)
    sq.row_factory = sqlite3.Row
    try:
        usuarios = sq.execute("SELECT * FROM usuarios").fetchall()
        suscripciones = sq.execute("SELECT * FROM suscripciones").fetchall()
    finally:
        sq.close()

    cur = conn_pg.cursor()

    # --- usuarios: UPSERT por email, preservando el id del SQLite. ---------
    for u in usuarios:
        cur.execute(
            """
            INSERT INTO usuarios (id, nombre, email, password_hash, tipo_usuario, fecha_registro)
            OVERRIDING SYSTEM VALUE
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (email) DO UPDATE SET
                nombre         = EXCLUDED.nombre,
                password_hash  = EXCLUDED.password_hash,
                tipo_usuario   = EXCLUDED.tipo_usuario,
                fecha_registro = EXCLUDED.fecha_registro;
            """,
            (u["id"], u["nombre"], u["email"], u["password_hash"],
             u["tipo_usuario"], u["fecha_registro"]),
        )

    # --- suscripciones: UPSERT por id, re-mapeando usuario_id por email y ---
    # --- preservando plan/estado/fechas reales del SQLite. -----------------
    for s in suscripciones:
        # email del usuario dueño de esta suscripción (según SQLite)
        fila_email = sq_email = None
        for u in usuarios:
            if u["id"] == s["usuario_id"]:
                sq_email = u["email"]
                break
        if sq_email is None:
            _abortar(
                f"La suscripción id={s['id']} referencia usuario_id={s['usuario_id']} "
                "inexistente en el SQLite origen."
            )
        cur.execute("SELECT id FROM usuarios WHERE email = %s;", (sq_email,))
        fila = cur.fetchone()
        if not fila:
            _abortar(f"No se encontró en Postgres el usuario con email {sq_email!r}.")
        usuario_id_pg = fila["id"]

        cur.execute(
            """
            INSERT INTO suscripciones (id, usuario_id, plan, estado, fecha_inicio, fecha_vencimiento)
            OVERRIDING SYSTEM VALUE
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                usuario_id        = EXCLUDED.usuario_id,
                plan              = EXCLUDED.plan,
                estado            = EXCLUDED.estado,
                fecha_inicio      = EXCLUDED.fecha_inicio,
                fecha_vencimiento = EXCLUDED.fecha_vencimiento;
            """,
            (s["id"], usuario_id_pg, s["plan"], s["estado"],
             s["fecha_inicio"], s["fecha_vencimiento"]),
        )

    # --- resincronizar secuencias para que las altas futuras no colisionen -
    cur.execute(
        "SELECT setval(pg_get_serial_sequence('usuarios','id'), "
        "(SELECT COALESCE(MAX(id), 1) FROM usuarios));"
    )
    cur.execute(
        "SELECT setval(pg_get_serial_sequence('suscripciones','id'), "
        "(SELECT COALESCE(MAX(id), 1) FROM suscripciones));"
    )

    conn_pg.commit()
    print(f"[3] Auth migrada: usuarios={len(usuarios)}, suscripciones={len(suscripciones)} "
          "(ids y valores preservados).")


# =========================================================================
# PASO 4 — Migrar CSV con datos: emprendedoras (UPSERT por Email),
#          productos y finanzas (reemplazo total). CSV vacíos: nada.
# =========================================================================
def _castear_numerico(df, tabla, columna):
    """Castea una columna a numérico con errors='raise'. Ante dato corrupto,
    aborta con detalle de tabla/columna/fila (sin convertir a NULL en silencio)."""
    try:
        return pd.to_numeric(df[columna], errors="raise")
    except (ValueError, TypeError) as exc:
        # localizar la primera fila ofensora para el reporte
        for idx, val in df[columna].items():
            try:
                pd.to_numeric(pd.Series([val]), errors="raise")
            except (ValueError, TypeError):
                _abortar(
                    f"MISMATCH numérico en {tabla}.{columna}: fila {idx} "
                    f"con valor {val!r} no es numérico ({exc})."
                )
        _abortar(f"MISMATCH numérico en {tabla}.{columna}: {exc}")


def paso_4_migrar_csv(conn_pg):
    # --- emprendedoras: UPSERT por "Email" con execute_values ---------------
    if os.path.exists(_CSV_EMPRENDEDORAS):
        df_emp = pd.read_csv(_CSV_EMPRENDEDORAS)
    else:
        df_emp = pd.DataFrame(columns=database._COLUMNAS_POR_TABLA["emprendedoras"])

    cols = database._COLUMNAS_POR_TABLA["emprendedoras"]  # 22 columnas, nombres reales
    df_emp = df_emp.reindex(columns=cols)
    # NaN -> None para que psycopg2 inserte NULL donde falte.
    df_emp = df_emp.astype(object).where(pd.notna(df_emp), None)

    if len(df_emp) > 0:
        cur = conn_pg.cursor()
        col_list = ", ".join(f'"{c}"' for c in cols)
        set_list = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in cols if c != "Email")
        sql = (f'INSERT INTO emprendedoras ({col_list}) VALUES %s '
               f'ON CONFLICT ("Email") DO UPDATE SET {set_list}')
        filas = [tuple(r[c] for c in cols) for _, r in df_emp.iterrows()]
        execute_values(cur, sql, filas)
        conn_pg.commit()
    print(f"[4a] emprendedoras migradas por UPSERT (filas={len(df_emp)}).")

    # --- productos: reemplazo total (TRUNCATE + append) ---------------------
    if os.path.exists(_CSV_PRODUCTOS):
        df_prod = pd.read_csv(_CSV_PRODUCTOS)
        if len(df_prod) > 0:
            df_prod["Precio"] = _castear_numerico(df_prod, "productos", "Precio")
        database.reemplazar_tabla_desde_df("productos", df_prod)
    print("[4b] productos migrados (reemplazo total).")

    # --- finanzas: reemplazo total (TRUNCATE + append) ----------------------
    if os.path.exists(_CSV_FINANZAS):
        df_fin = pd.read_csv(_CSV_FINANZAS)
        if len(df_fin) > 0:
            df_fin["Monto"] = _castear_numerico(df_fin, "finanzas", "Monto")
        database.reemplazar_tabla_desde_df("finanzas", df_fin)
    print("[4c] finanzas migradas (reemplazo total).")

    # --- CSV vacíos: nada que insertar (tablas ya creadas en el paso 2) -----
    print("[4d] CSV vacíos (agenda, tareas, evaluaciones, oraciones, "
          "lives_grabados, chat_live, publicaciones_muro, clientes): sin filas.")


# =========================================================================
# PASO 5 — Reporte de conteos ORIGEN vs POSTGRES por tabla + agregados.
# =========================================================================
def paso_5_reporte_conteos(conn_pg):
    sq = sqlite3.connect(_SQLITE)
    cur_sq = sq.cursor()
    cur_pg = conn_pg.cursor()

    print()
    print(f"{'TABLA':<22}{'ORIGEN':>8}{'POSTGRES':>10}{'   RESULTADO'}")
    print("-" * 54)

    ok_global = True
    total_filas_pg = 0
    try:
        for tabla in _TABLAS_DATOS:
            if tabla in ("usuarios", "suscripciones"):
                origen = _contar_origen_sqlite(cur_sq, tabla)
            else:
                origen = _contar_origen_csv(tabla)
            postgres = _contar_postgres(cur_pg, tabla)
            total_filas_pg += postgres
            resultado = "OK" if origen == postgres else "MISMATCH"
            if resultado == "MISMATCH":
                ok_global = False
            etiqueta = f"{tabla} (SQLite)" if tabla == "usuarios" else tabla
            print(f"{etiqueta:<22}{origen:>8}{postgres:>10}   {resultado}")
    finally:
        sq.close()

    print("-" * 54)

    # Agregado 1: número de tablas creadas (debe ser 14 = 13 datos + anuncios).
    cur_pg.execute(
        "SELECT COUNT(*) FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = ANY(%s);",
        (_TABLAS_DATOS + ["anuncios"],),
    )
    tablas_creadas = cur_pg.fetchone()["count"]
    ok_tablas = (tablas_creadas == 14)
    print(f"TABLAS CREADAS: {tablas_creadas} (esperado 14){'':<6}"
          f"{'OK' if ok_tablas else 'MISMATCH'}")

    # Agregado 2: total de filas de datos (debe ser 6).
    ok_filas = (total_filas_pg == 6)
    print(f"TOTAL FILAS DE DATOS: {total_filas_pg} (esperado 6){'':<2}"
          f"{'OK' if ok_filas else 'MISMATCH'}")

    if not (ok_global and ok_tablas and ok_filas):
        _abortar("Verificación de CONTEOS fallida (ver reporte arriba).")
    print("[5] Conteos y agregados OK.")


# =========================================================================
# PASO 6 — Aserciones de VALOR (exit != 0 ante cualquier discrepancia).
# =========================================================================
def paso_6_aserciones_valor(conn_pg):
    sq = sqlite3.connect(_SQLITE)
    sq.row_factory = sqlite3.Row
    try:
        u_sq = sq.execute(
            "SELECT * FROM usuarios WHERE email = ?;", (database.CORREO_ADMIN,)
        ).fetchone()
        if u_sq is None:
            _abortar(f"No se encontró el usuario admin {database.CORREO_ADMIN!r} en el SQLite.")
        s_sq = sq.execute(
            "SELECT * FROM suscripciones WHERE usuario_id = ?;", (u_sq["id"],)
        ).fetchone()
    finally:
        sq.close()

    cur = conn_pg.cursor()

    # 6.1 Suscripción admin: plan/estado/fecha_inicio/fecha_vencimiento exactos.
    cur.execute(
        """
        SELECT s.plan, s.estado, s.fecha_inicio, s.fecha_vencimiento
        FROM suscripciones s
        JOIN usuarios u ON u.id = s.usuario_id
        WHERE u.email = %s;
        """,
        (database.CORREO_ADMIN,),
    )
    s_pg = cur.fetchone()
    if s_pg is None:
        _abortar("No se encontró la suscripción del admin en Postgres.")
    for campo in ("plan", "estado", "fecha_inicio", "fecha_vencimiento"):
        if str(s_sq[campo]) != str(s_pg[campo]):
            _abortar(
                f"MISMATCH DE VALOR en suscripcion.{campo}: "
                f"SQLite={s_sq[campo]!r} vs Postgres={s_pg[campo]!r}."
            )

    # 6.2 Usuario admin: nombre/tipo_usuario/fecha_registro/password_hash exactos.
    cur.execute(
        "SELECT nombre, tipo_usuario, fecha_registro, password_hash "
        "FROM usuarios WHERE email = %s;",
        (database.CORREO_ADMIN,),
    )
    u_pg = cur.fetchone()
    if u_pg is None:
        _abortar("No se encontró el usuario admin en Postgres.")
    for campo in ("nombre", "tipo_usuario", "fecha_registro", "password_hash"):
        if str(u_sq[campo]) != str(u_pg[campo]):
            _abortar(
                f"MISMATCH DE VALOR en usuario.{campo}: "
                f"SQLite={u_sq[campo]!r} vs Postgres={u_pg[campo]!r}."
            )

    # 6.3 emprendedoras.Foto_Perfil: igualdad de longitud Y de hash SHA-256.
    if os.path.exists(_CSV_EMPRENDEDORAS):
        df_emp = pd.read_csv(_CSV_EMPRENDEDORAS)
        if len(df_emp) > 0:
            for _, fila in df_emp.iterrows():
                email = fila["Email"]
                foto_csv = "" if pd.isna(fila.get("Foto_Perfil")) else str(fila["Foto_Perfil"])
                cur.execute(
                    'SELECT "Foto_Perfil" FROM emprendedoras WHERE "Email" = %s;', (email,)
                )
                r = cur.fetchone()
                if r is None:
                    _abortar(f"MISMATCH DE VALOR: emprendedora {email!r} ausente en Postgres.")
                foto_pg = "" if r["Foto_Perfil"] is None else str(r["Foto_Perfil"])
                if len(foto_csv) != len(foto_pg):
                    _abortar(
                        f"MISMATCH DE VALOR en Foto_Perfil ({email}): "
                        f"len CSV={len(foto_csv)} vs len Postgres={len(foto_pg)}."
                    )
                h_csv = hashlib.sha256(foto_csv.encode("utf-8")).hexdigest()
                h_pg = hashlib.sha256(foto_pg.encode("utf-8")).hexdigest()
                if h_csv != h_pg:
                    _abortar(
                        f"MISMATCH DE VALOR en Foto_Perfil ({email}): "
                        "el hash SHA-256 no coincide (foto alterada/truncada)."
                    )

    # 6.4 productos.Precio: igualdad numérica por fila (orden determinista).
    _comparar_numerico_por_fila(
        cur, "productos", "Precio", _CSV_PRODUCTOS,
        orden=["Producto", "Email_Emprendedora"],
    )

    # 6.5 finanzas.Monto: igualdad numérica por fila (orden determinista).
    _comparar_numerico_por_fila(
        cur, "finanzas", "Monto", _CSV_FINANZAS,
        orden=["Fecha", "Concepto"],
    )

    print("[6] Aserciones de VALOR OK.")


def _comparar_numerico_por_fila(cur, tabla, columna, ruta_csv, orden):
    if not os.path.exists(ruta_csv):
        return
    df = pd.read_csv(ruta_csv)
    if len(df) == 0:
        return
    esperado = pd.to_numeric(df[columna], errors="raise")
    df = df.assign(**{columna: esperado}).sort_values(orden).reset_index(drop=True)

    orden_sql = ", ".join(f'"{c}"' for c in orden)
    cur.execute(f'SELECT "{columna}" FROM {tabla} ORDER BY {orden_sql};')
    valores_pg = [float(r[columna]) for r in cur.fetchall()]

    valores_csv = [float(v) for v in df[columna].tolist()]
    if len(valores_csv) != len(valores_pg):
        _abortar(
            f"MISMATCH DE VALOR en {tabla}.{columna}: "
            f"{len(valores_csv)} filas CSV vs {len(valores_pg)} filas Postgres."
        )
    for i, (a, b) in enumerate(zip(valores_csv, valores_pg)):
        if round(a, 2) != round(b, 2):
            _abortar(
                f"MISMATCH DE VALOR en {tabla}.{columna} (fila ordenada {i}): "
                f"CSV={a} vs Postgres={b}."
            )


# =========================================================================
# ORQUESTACIÓN
# =========================================================================
def main():
    paso_0_precondicion()
    paso_1_resolver_db_url()
    paso_2_inicializar()

    conn_pg = database.obtener_conexion()
    try:
        paso_3_migrar_auth(conn_pg)
        paso_4_migrar_csv(conn_pg)
        paso_5_reporte_conteos(conn_pg)
        paso_6_aserciones_valor(conn_pg)
    finally:
        conn_pg.close()

    print()
    print("MIGRACION OK")
    sys.exit(0)


if __name__ == "__main__":
    main()
