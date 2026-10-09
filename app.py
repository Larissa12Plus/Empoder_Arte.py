"""
=============================================================================
PROYECTO: EMPODER-ARTE (Plataforma Nacional de Emprendedoras, Ventas y Capacitación)
ARCHIVO: app.py
AUTORA & FUNDADORA: Larissa García
DESCRIPCIÓN: Aplicación en Streamlit con menú lateral rosa, registro directo VIP,
             reseteo de contraseñas, baja/eliminación de usuarios, edición y eliminación de
             productos en Marketplace (restringido a dueña o administradora), categorías
             dinámicas de productos/servicios con alta manual y guardado automático tanto
             en Marketplace como en Registro de Emprendedoras, eliminación de
             transacciones en finanzas, peticiones de oración categorizadas con celular,
             guardado de lives por 5 días, casilla obligatoria de privacidad, sistema de
             evaluaciones con estrellas y amplio catálogo de versículos bíblicos.
=============================================================================
"""
import streamlit as st
import pandas as pd
import numpy as np
import os
import base64
import json
import hashlib
import subprocess
import random
import time
from io import BytesIO
from datetime import datetime, date, timedelta
from PIL import Image
import pydeck as pdk
from cryptography.fernet import Fernet
import database as db  # Capa SQLite: auth + suscripciones (fuente de verdad)

# ---------------------------------------------------------
# 0. SISTEMA DE AUTENTICACIÓN Y GESTIÓN DE USUARIOS
# ---------------------------------------------------------
ARCHIVO_USUARIOS = "usuarios.json"
ARCHIVO_SESION = "session.json"
ARCHIVO_CATEGORIAS = "categorias_dinamicas.json"
CORREO_ADMIN = "garcialarissa1292@gmail.com"
NOMBRE_FUNDADORA = "Larissa García"
# La contraseña de admin NO se hardcodea: se resuelve con precedencia
# ADMIN_PASS (entorno) -> st.secrets['ADMIN_PASS'] -> .streamlit/secrets.toml,
# reutilizando el resolvedor de la capa de datos (db._resolver_admin_pass).
PASS_ADMIN_PLANA = db.PASS_ADMIN_PLANA

def generar_hash(password: str) -> str:
    """Genera un hash SHA-256 seguro para almacenar contraseñas."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def cargar_usuarios_db() -> dict:
    """Carga el diccionario de usuarios desde el archivo JSON."""
    if os.path.exists(ARCHIVO_USUARIOS):
        try:
            with open(ARCHIVO_USUARIOS, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def guardar_usuarios_db(usuarios: dict):
    """Guarda el diccionario de usuarios en el archivo JSON."""
    with open(ARCHIVO_USUARIOS, "w", encoding="utf-8") as f:
        json.dump(usuarios, f, indent=4, ensure_ascii=False)

def inicializar_usuarios_base():
    """Crea o fuerza la actualización del usuario administrador principal."""
    usuarios = cargar_usuarios_db()
    usuarios[CORREO_ADMIN] = {
        "nombre": "Larissa García (Fundadora)",
        "password_hash": generar_hash(PASS_ADMIN_PLANA),
        "rol": "Admin",
        "activo": True
    }
    guardar_usuarios_db(usuarios)

def validar_sesion_diaria():
    """Verifica si existe una sesión iniciada el día de hoy."""
    if os.path.exists(ARCHIVO_SESION):
        try:
            with open(ARCHIVO_SESION, "r", encoding="utf-8") as f:
                datos_sesion = json.load(f)
            fecha_sesion = datos_sesion.get("fecha")
            fecha_hoy = date.today().strftime("%Y-%m-%d")
            if fecha_sesion == fecha_hoy:
                return datos_sesion
        except Exception:
            return None
    return None

def guardar_sesion_diaria(email: str, nombre: str, rol: str):
    """Guarda la sesión del usuario para no solicitar login de nuevo hoy."""
    datos_sesion = {
        "email": email,
        "nombre": nombre,
        "rol": rol,
        "fecha": date.today().strftime("%Y-%m-%d")
    }
    with open(ARCHIVO_SESION, "w", encoding="utf-8") as f:
        json.dump(datos_sesion, f, indent=4, ensure_ascii=False)

def cerrar_sesion_local():
    """Elimina la sesión local diaria."""
    if os.path.exists(ARCHIVO_SESION):
        os.remove(ARCHIVO_SESION)

# ---------------------------------------------------------
# GESTIÓN DE CATEGORÍAS DINÁMICAS (ALTA MANUAL Y GUARDADO AUTOMÁTICO)
# ---------------------------------------------------------
CATEGORIAS_SERVICIOS_BASE = ["Belleza y Estética", "Diseño y Creatividad", "Consultoría y Asesoría", "Eventos y Fotografía", "Reparaciones y Confección", "Educación y Clases", "Otro Servicio"]
CATEGORIAS_PRODUCTOS_BASE = ["Postres y Repostería", "Cuidado Personal y Cosmética", "Moda y Accesorios", "Decoración y Hogar", "Papelería y Agendas", "Artesanías y Manualidades", "Otro Producto"]

def cargar_categorias_db() -> dict:
    if os.path.exists(ARCHIVO_CATEGORIAS):
        try:
            with open(ARCHIVO_CATEGORIAS, "r", encoding="utf-8") as f:
                cats = json.load(f)
                if "servicios" not in cats: cats["servicios"] = CATEGORIAS_SERVICIOS_BASE
                if "productos" not in cats: cats["productos"] = CATEGORIAS_PRODUCTOS_BASE
                return cats
        except Exception:
            return {"servicios": CATEGORIAS_SERVICIOS_BASE, "productos": CATEGORIAS_PRODUCTOS_BASE}
    return {"servicios": CATEGORIAS_SERVICIOS_BASE, "productos": CATEGORIAS_PRODUCTOS_BASE}

def guardar_categorias_db(cats: dict):
    with open(ARCHIVO_CATEGORIAS, "w", encoding="utf-8") as f:
        json.dump(cats, f, indent=4, ensure_ascii=False)

def agregar_categoria_dinamica(tipo: str, nueva_cat: str):
    nueva_cat = nueva_cat.strip()
    if not nueva_cat:
        return
    cats = cargar_categorias_db()
    if tipo in cats:
        if nueva_cat not in cats[tipo]:
            cats[tipo].insert(len(cats[tipo]) - 1, nueva_cat)
            guardar_categorias_db(cats)

# ---------------------------------------------------------
# 1. SISTEMA DE CIFRADO Y SEGURIDAD DE DATOS (AES-128 / Fernet)
# ---------------------------------------------------------
CLAVE_LLAVE_FILE = "secret.key"

def obtener_o_crear_clave():
    if os.path.exists(CLAVE_LLAVE_FILE):
        with open(CLAVE_LLAVE_FILE, "rb") as key_file:
            return key_file.read()
    else:
        key = Fernet.generate_key()
        with open(CLAVE_LLAVE_FILE, "wb") as key_file:
            key_file.write(key)
        return key

KEY_CIFRADO = obtener_o_crear_clave()
cipher_suite = Fernet(KEY_CIFRADO)

def cifrar_dato(texto: str) -> str:
    """Cifra un texto plano y devuelve una cadena en formato string seguro."""
    if not texto or texto == "N/A":
        return "N/A"
    try:
        texto_bytes = str(texto).encode('utf-8')
        cifrado_bytes = cipher_suite.encrypt(texto_bytes)
        return cifrado_bytes.decode('utf-8')
    except Exception:
        return texto

def descifrar_dato(texto_cifrado: str) -> str:
    """Descifra una cadena cifrada y devuelve el texto plano original."""
    if not texto_cifrado or texto_cifrado in ["N/A", "Validado", "Pendiente", "Subido / En Revisión"]:
        return texto_cifrado
    try:
        bytes_cifrados = str(texto_cifrado).encode('utf-8')
        descifrado_bytes = cipher_suite.decrypt(bytes_cifrados)
        return descifrado_bytes.decode('utf-8')
    except Exception:
        return texto_cifrado

# ---------------------------------------------------------
# 2. CONFIGURACIÓN DE BASES DE DATOS Y COORDENADAS
# ---------------------------------------------------------
ARCHIVO_CSV = "emprendedoras.csv"
ARCHIVO_CHAT = "chat_live.csv"
ARCHIVO_FINANZAS = "finanzas.csv"
ARCHIVO_PRODUCTOS = "productos.csv"
ARCHIVO_ORACIONES = "oraciones.csv"
ARCHIVO_AGENDA = "agenda.csv"
ARCHIVO_TAREAS = "tareas.csv"
ARCHIVO_EVALUACIONES = "evaluaciones.csv"
ARCHIVO_LIVES = "lives_grabados.csv"
LOGO_IMAGEN = "Empoder Arte Order_blanco_2.png"
FOTO_DEFAULT = "https://picsum.photos/150"

ESTADOS_MEXICO = [
    "Aguascalientes", "Baja California", "Baja California Sur", "Campeche",
    "Chiapas", "Chihuahua", "Ciudad de México", "Coahuila", "Colima", "Durango",
    "Estado de México", "Guanajuato", "Guerrero", "Hidalgo", "Jalisco", "Michoacán",
    "Morelos", "Nayarit", "Nuevo León", "Oaxaca", "Puebla", "Querétaro",
    "Quintana Roo", "San Luis Potosí", "Sinaloa", "Sonora", "Tabasco",
    "Tamaulipas", "Tlaxcala", "Veracruz", "Yucatán", "Zacatecas"
]

COORDENADAS_ESTADOS = {
    "Aguascalientes": (21.8853, -102.2916), "Baja California": (30.8406, -115.2838),
    "Baja California Sur": (26.0444, -111.6661), "Campeche": (19.8301, -90.5349),
    "Chiapas": (16.7569, -93.1292), "Chihuahua": (28.6330, -106.0691),
    "Ciudad de México": (19.4326, -99.1332), "Coahuila": (27.0587, -101.7068),
    "Colima": (19.2452, -103.7241), "Durango": (24.0277, -104.6532),
    "Estado de México": (19.4969, -99.7233), "Guanajuato": (21.0190, -101.2574),
    "Guerrero": (17.4392, -99.5451), "Hidalgo": (20.0911, -98.7624),
    "Jalisco": (20.6597, -103.3496), "Michoacán": (19.5665, -101.7068),
    "Morelos": (18.6813, -99.1013), "Nayarit": (21.7514, -104.8455),
    "Nuevo León": (25.6866, -100.3161), "Oaxaca": (17.0732, -96.7266),
    "Puebla": (19.0414, -98.2063), "Querétaro": (20.5888, -100.3899),
    "Quintana Roo": (19.1817, -88.4791), "San Luis Potosí": (22.1565, -100.9855),
    "Sinaloa": (25.1721, -107.4795), "Sonora": (29.0729, -110.9559),
    "Tabasco": (17.8409, -92.6189), "Tamaulipas": (24.2669, -98.8363),
    "Tlaxcala": (19.3182, -98.2375), "Veracruz": (19.1738, -96.1342),
    "Yucatán": (20.9674, -89.5926), "Zacatecas": (22.7709, -102.5528)
}

VERSICULOS_EMPRENDIMIENTO = [
    {"texto": "¿Has visto hombre solícito en su obra? Delante de los reyes estará; no estará delante de los de baja suerte.", "cita": "Proverbios 22:29"},
    {"texto": "Sabiduría ante todo: adquiere sabiduría; y ante toda tu posesión adquiere inteligencia.", "cita": "Proverbios 4:7"},
    {"texto": "Por el placer se hace el convite, y el vino alegra los vivos: y el dinero responde á todo.", "cita": "Eclesiastés 10:19"},
    {"texto": "Porque escudo es la ciencia, y escudo es el dinero: mas la sabiduría excede en que da vida á sus poseedores.", "cita": "Eclesiastés 7:12"},
    {"texto": "JEHOVÁ es mi pastor; nada me faltará. En lugares de delicados pastos me hará yacer: junto á aguas de reposo me pastoreará. Confortará mi alma; guiaráme por sendas de justicia por amor de su nombre.", "cita": "Salmo 23:1-3"},
    {"texto": "Antes acuérdate de Jehová tu Dios: porque él te da el poder para hacer las riquezas, á fin de confirmar su pacto que juró á tus padres, como en este día.", "cita": "Deuteronomio 8:18"},
    {"texto": "Y llegando también el que había recibido un talento, dijo: Señor, te conocía que eres hombre duro... Y respondiendo su señor, le dijo: Malo y negligente siervo... Quitadle pues el talento, y dadlo al que tiene diez talentos.", "cita": "Mateo 25:24-30"},
    {"texto": "Y á vosotros multiplique el Señor, y haga abundar el amor entre vosotros, y para con todos, como es también de nosotros para con vosotros;", "cita": "1 Tesalonicenses 3:12"},
    {"texto": "Encomienda á Jehová tus obras, y tus pensamientos serán afirmados.", "cita": "Proverbios 16:3"},
    {"texto": "El libro de aquesta ley nunca se apartará de tu boca: antes de día y de noche meditarás en él... porque entonces harás prosperar tu camino, y todo te saldrá bien.", "cita": "Josué 1:8"},
    {"texto": "Y si en lo ajeno no fuisteis fieles, ¿quién os dará lo que es vuestro?", "cita": "Lucas 16:12"},
    {"texto": "Sembrad para vosotros en justicia, segad para vosotros en misericordia; arad para vosotros barbecho: porque es el tiempo de buscar á Jehová, hasta que venga y os enseñe justicia.", "cita": "Oseas 10:12"},
    {"texto": "En el cuidado no perezosos; ardientes en espíritu; sirviendo al Señor;", "cita": "Romanos 12:11"},
    {"texto": "Riquezas, y honra, y vida, son la remuneración de la humildad y del temor de Jehová.", "cita": "Proverbios 22:4"},
    {"texto": "Y si algún reino contra sí mismo fuere dividido, no puede permanecer el tal reino.", "cita": "Marcos 3:24"},
    {"texto": "No tuerzas el derecho; no hagas acepción de personas, ni tomes soborno; porque el soborno ciega los ojos de los sabios, y pervierte las palabras de los justos.", "cita": "Deuteronomio 16:19"},
    {"texto": "Y todo lo que hagáis, hacedlo de ánimo, como al Señor, y no á los hombres;", "cita": "Colosenses 3:23"},
    {"texto": "Disminuiránse las riquezas de vanidad: empero multiplicará el que allega con su mano.", "cita": "Proverbios 13:11"},
    {"texto": "Fíate de Jehová de todo tu corazón, y no te estribes en tu prudencia. Reconócelo en todos tus caminos, y él enderezará tus veredas.", "cita": "Proverbios 3:5-6"},
    {"texto": "La mano negligente hace pobre: mas la mano de los diligentes enriquece.", "cita": "Proverbios 10:4"},
    {"texto": "En toda labor hay fruto: mas la palabra de los labios solamente empobrece.", "cita": "Proverbios 14:23"},
    {"texto": "Responderion y dijéronle: ¿Qué haremos para que obremos las obras de Dios? Respondió Jesús, y díjoles: Esta es la obra de Dios, que creáis en el que él ha enviado.", "cita": "Juan 6:28-29"},
    {"texto": "Porque no nos ha dado Dios el espíritu de temor, sino el de fortaleza, y de amor, y de templanza.", "cita": "2 Timoteo 1:7"},
    {"texto": "Mejor es lo poco con justicia, que la muchedumbre de frutos sin derecho.", "cita": "Proverbios 16:8"},
    {"texto": "Así ha dicho Jehová, Redentor tuyo, el Santo de Israel: Yo Jehová Dios tuyo, que te enseña provechosamente, que te encamina por el camino que andas.", "cita": "Isaías 48:17"},
    {"texto": "Porque yo sé los pensamientos que tengo acerca de vosotros, dice Jehová, pensamientos de paz, y no de mal, para daros el fin que esperáis.", "cita": "Jeremías 29:11"},
    {"texto": "Desea, y nada alcanza el alma del perezoso: mas el alma de los diligentes será engordada.", "cita": "Proverbios 13:4"},
    {"texto": "Si pues coméis, ó bebéis, ó hacéis otra cosa, hacedlo todo á gloria de Dios.", "cita": "1 Corintios 10:31"},
    {"texto": "El hombre de bien tiene misericordia y presta; gobierna sus cosas con juicio.", "cita": "Salmo 112:5"},
    {"texto": "Ella hace telas de lino y las vende, y provee cinturones a los comerciantes. Fuerza y dignidad son su vestidura.", "cita": "Proverbios 31:24-25"}
]

AREAS_ORACION = ["Negocio", "Trabajo", "Familia", "Pareja o Esposos", "Hijos", "Emociones Personales"]

# ---------------------------------------------------------
# FUNCIONES AUXILIARES Y MANEJO DE DATOS
# ---------------------------------------------------------
def cargar_imagen_segura(ruta):
    if os.path.exists(ruta):
        try:
            return Image.open(ruta)
        except Exception:
            return None
    return None

def convertir_imagen_a_base64(uploaded_file):
    if uploaded_file is not None:
        try:
            bytes_data = uploaded_file.getvalue()
            if not bytes_data:
                return FOTO_DEFAULT
            image = Image.open(BytesIO(bytes_data))
            if image.mode in ("RGBA", "P"):
                image = image.convert("RGB")
            image.thumbnail((300, 300))
            buffered = BytesIO()
            image.save(buffered, format="JPEG", quality=85)
            img_b64_str = base64.b64encode(buffered.getvalue()).decode("utf-8").replace("\n", "").replace("\r", "")
            return f"data:image/jpeg;base64,{img_b64_str}"
        except Exception:
            return FOTO_DEFAULT
    return FOTO_DEFAULT

def crear_df_inicial_fundadora():
    lat, lon = COORDENADAS_ESTADOS["Querétaro"]
    curp_cifrada = cifrar_dato("GAGL921211XXXXXX00")
    ine_cifrada = cifrar_dato("Validado")
    return pd.DataFrame([{
        "Email": CORREO_ADMIN,
        "Celular": "No proporcionado",
        "Nombre": NOMBRE_FUNDADORA,
        "Negocio": "Empoder-Arte (Fundadora)",
        "Tipo_Oferta": "Servicios",
        "Categoria": "Consultoría y Asesoría",
        "Estado": "Querétaro",
        "Ciudad": "Santiago de Querétaro",
        "Colonia": "Centro",
        "Contacto": CORREO_ADMIN,
        "Descripcion": "Plataforma oficial de la comunidad de emprendedoras.",
        "Historia": "Fundadora de la red nacional Empoder-Arte para impulsar el talento de mujeres emprendedoras.",
        "Estado_Pago": "Administradora",
        "Metodo_Pago": "Fundadora",
        "Estado_Aprobacion": "Aprobado",
        "Foto_Perfil": FOTO_DEFAULT,
        "INE_Doc": ine_cifrada,
        "CURP_Valor": curp_cifrada,
        "lat": lat,
        "lon": lon
    }])

def cargar_datos():
    # 22 columnas reales de la tabla 'emprendedoras' (orden determinista que ve la app).
    columnas_esperadas = ["Email", "Nombre", "Negocio", "Tipo_Oferta", "Categoria", "WhatsApp",
                          "Descripcion", "Estado_Pago", "Metodo_Pago", "Contacto", "Estado_Aprobacion",
                          "Estado", "Ciudad", "Colonia", "lat", "lon", "Celular", "INE_Doc", "CURP_Doc",
                          "Historia", "CURP_Valor", "Foto_Perfil"]
    try:
        df = pd.read_sql("SELECT * FROM emprendedoras", db._get_engine())
        if "id" in df.columns:
            df = df.drop(columns=["id"])

        if df.empty:
            # Tabla vacía: usar la semilla de la fundadora, reindexada a las 22 columnas.
            df = crear_df_inicial_fundadora().reindex(columns=columnas_esperadas)
            for col in columnas_esperadas:
                default = "" if col != "CURP_Doc" else "No proporcionado"
                df[col] = df[col].fillna(default)
            return df[columnas_esperadas]

        # Añadir columnas faltantes con su default actual.
        for col in columnas_esperadas:
            if col not in df.columns:
                df[col] = "Querétaro" if col == "Estado" else ("Aprobado" if col == "Estado_Aprobacion" else (FOTO_DEFAULT if col == "Foto_Perfil" else "Por definir"))

        df["Foto_Perfil"] = df["Foto_Perfil"].fillna(FOTO_DEFAULT)
        df.loc[df["Foto_Perfil"].astype(str).str.contains("via.placeholder.com", na=False), "Foto_Perfil"] = FOTO_DEFAULT

        # lat/lon derivados de Estado (solo en memoria, se recomputan en cada carga).
        df["lat"] = df["Estado"].map(lambda x: COORDENADAS_ESTADOS.get(str(x), (23.6345, -102.5528))[0])
        df["lon"] = df["Estado"].map(lambda x: COORDENADAS_ESTADOS.get(str(x), (23.6345, -102.5528))[1])

        # Fix admin (solo en memoria): nombre y aprobación de la fundadora.
        mask_admin = df["Email"] == CORREO_ADMIN
        if mask_admin.any():
            df.loc[mask_admin, "Nombre"] = NOMBRE_FUNDADORA
            df.loc[mask_admin, "Estado_Aprobacion"] = "Aprobado"

        return df[columnas_esperadas]
    except Exception:
        df_i = crear_df_inicial_fundadora().reindex(columns=columnas_esperadas)
        for col in columnas_esperadas:
            default = "" if col != "CURP_Doc" else "No proporcionado"
            df_i[col] = df_i[col].fillna(default)
        return df_i[columnas_esperadas]

def cargar_productos():
    df_base_prods = pd.DataFrame([
        {
            "Email_Emprendedora": CORREO_ADMIN,
            "Producto": "Kit de Velas Artesanales",
            "Precio": 250.0,
            "Categoria": "Decoración y Hogar",
            "Estado": "Querétaro",
            "Stock": 10,
            "Estado_Aprobacion": "Aprobado",
            "Foto_Producto": "https://picsum.photos/300/200"
        },
        {
            "Email_Emprendedora": CORREO_ADMIN,
            "Producto": "Agenda Empoder-Arte 2026",
            "Precio": 380.0,
            "Categoria": "Papelería y Agendas",
            "Estado": "Querétaro",
            "Stock": 5,
            "Estado_Aprobacion": "Aprobado",
            "Foto_Producto": "https://picsum.photos/300/200"
        }
    ])
    columnas_esperadas = ["Email_Emprendedora", "Producto", "Precio", "Categoria", "Stock",
                          "Estado_Aprobacion", "Estado", "Foto_Producto"]
    try:
        df_p = pd.read_sql("SELECT * FROM productos", db._get_engine())
        if "id" in df_p.columns:
            df_p = df_p.drop(columns=["id"])
        if df_p.empty:
            return df_base_prods[columnas_esperadas]
        if "Estado_Aprobacion" not in df_p.columns:
            df_p["Estado_Aprobacion"] = "Aprobado"
        if "Estado" not in df_p.columns:
            df_p["Estado"] = "Querétaro"
        if "Foto_Producto" not in df_p.columns:
            df_p["Foto_Producto"] = "https://picsum.photos/300/200"
        return df_p[columnas_esperadas]
    except Exception:
        return df_base_prods[columnas_esperadas]

def cargar_chat_live():
    columnas_esperadas = ["Hora", "Usuario", "Mensaje"]
    try:
        df = pd.read_sql("SELECT * FROM chat_live", db._get_engine())
        if "id" in df.columns:
            df = df.drop(columns=["id"])
        for col in columnas_esperadas:
            if col not in df.columns:
                df[col] = ""
        return df[columnas_esperadas]
    except Exception:
        return pd.DataFrame(columns=columnas_esperadas)

def cargar_oraciones():
    columnas_esperadas = ["Fecha", "Nombre", "Email", "Celular", "Area", "Peticion", "Privada"]
    try:
        df = pd.read_sql("SELECT * FROM oraciones", db._get_engine())
        if "id" in df.columns:
            df = df.drop(columns=["id"])
        for col in columnas_esperadas:
            if col not in df.columns:
                df[col] = "General" if col == "Area" else "N/A"
        df["Area"] = df["Area"].fillna("General")
        return df[columnas_esperadas]
    except Exception:
        return pd.DataFrame(columns=columnas_esperadas)

def cargar_finanzas():
    columnas_esperadas = ["Fecha", "Email_Emprendedora", "Cliente", "Concepto", "Monto", "Tipo"]
    try:
        df = pd.read_sql("SELECT * FROM finanzas", db._get_engine())
        if "id" in df.columns:
            df = df.drop(columns=["id"])
        for col in columnas_esperadas:
            if col not in df.columns:
                df[col] = "General" if col == "Cliente" else "Sin especificar"
        return df[columnas_esperadas]
    except Exception:
        return pd.DataFrame(columns=columnas_esperadas)

def cargar_agenda():
    columnas_esperadas = ["Email_Emprendedora", "Fecha", "Hora", "Evento", "Cliente_Contacto", "Notas"]
    try:
        df = pd.read_sql("SELECT * FROM agenda", db._get_engine())
        if "id" in df.columns:
            df = df.drop(columns=["id"])
        for col in columnas_esperadas:
            if col not in df.columns:
                df[col] = "N/A"
        return df[columnas_esperadas]
    except Exception:
        return pd.DataFrame(columns=columnas_esperadas)

def cargar_tareas():
    columnas_esperadas = ["Email_Emprendedora", "Tarea", "Prioridad", "Estatus"]
    try:
        df = pd.read_sql("SELECT * FROM tareas", db._get_engine())
        if "id" in df.columns:
            df = df.drop(columns=["id"])
        for col in columnas_esperadas:
            if col not in df.columns:
                df[col] = "Pendiente ⏳" if col == "Estatus" else "N/A"
        df["Estatus"] = df["Estatus"].fillna("Pendiente ⏳")
        return df[columnas_esperadas]
    except Exception:
        return pd.DataFrame(columns=columnas_esperadas)

def cargar_evaluaciones():
    columnas_esperadas = ["Fecha", "Email_Destino", "Autor_Email", "Autor_Nombre", "Calificacion", "Comentario"]
    try:
        df = pd.read_sql("SELECT * FROM evaluaciones", db._get_engine())
        if "id" in df.columns:
            df = df.drop(columns=["id"])
        for col in columnas_esperadas:
            if col not in df.columns:
                df[col] = "Anonimo" if col == "Autor_Nombre" else "N/A"
        return df[columnas_esperadas]
    except Exception:
        return pd.DataFrame(columns=columnas_esperadas)

def cargar_lives_grabados():
    columnas_esperadas = ["Fecha_Emision", "Email_Emprendedora", "Nombre_Emprendedora", "Titulo_Live", "Frame_B64"]
    try:
        df = pd.read_sql("SELECT * FROM lives_grabados", db._get_engine())
        if "id" in df.columns:
            df = df.drop(columns=["id"])
        for col in columnas_esperadas:
            if col not in df.columns:
                df[col] = "N/A"
        df = df[columnas_esperadas]
        # Filtrar automáticos los de más de 5 días de antigüedad (solo en memoria).
        df["Fecha_Obj"] = pd.to_datetime(df["Fecha_Emision"], errors='coerce')
        hace_5_dias = pd.Timestamp.now() - pd.Timedelta(days=5)
        df = df[df["Fecha_Obj"] >= hace_5_dias].drop(columns=["Fecha_Obj"])
        return df
    except Exception:
        return pd.DataFrame(columns=columnas_esperadas)

# Mapea cada constante ARCHIVO_* a su tabla destino en Postgres. Es la única fuente
# de verdad de qué guardado corresponde a qué tabla (dispatcher de guardar_datos).
_MAPA_ARCHIVO_TABLA = {
    ARCHIVO_CSV: "emprendedoras",
    ARCHIVO_PRODUCTOS: "productos",
    ARCHIVO_FINANZAS: "finanzas",
    ARCHIVO_AGENDA: "agenda",
    ARCHIVO_TAREAS: "tareas",
    ARCHIVO_EVALUACIONES: "evaluaciones",
    ARCHIVO_ORACIONES: "oraciones",
    ARCHIVO_LIVES: "lives_grabados",
    ARCHIVO_CHAT: "chat_live",
}

def guardar_datos(df, archivo):
    """Reemplaza la tabla destino (según el nombre de 'archivo') con el DataFrame
    completo en Postgres. Si el destino no está mapeado, NO escribe un CSV huérfano:
    avisa y aborta el guardado."""
    tabla = _MAPA_ARCHIVO_TABLA.get(archivo)
    if tabla is None:
        st.error("Destino de guardado no reconocido.")
        print(f"[guardar_datos] archivo sin mapear a tabla: {archivo!r}")
        return
    try:
        db.reemplazar_tabla_desde_df(tabla, df)
    except Exception as e:
        st.error("No se pudieron guardar los cambios en la base de datos. "
                 "Verifica tu conexión e inténtalo de nuevo.")
        print(f"[guardar_datos] fallo al escribir '{tabla}': {e}")

def eliminar_usuario_definitivo(email_objetivo: str):
    """Elimina completamente un usuario de usuarios.json y emprendedoras.csv"""
    usuarios = cargar_usuarios_db()
    if email_objetivo in usuarios:
        del usuarios[email_objetivo]
        guardar_usuarios_db(usuarios)
    
    df_emp = cargar_datos()
    df_emp = df_emp[df_emp["Email"] != email_objetivo]
    guardar_datos(df_emp, ARCHIVO_CSV)

def mostrar_aviso_privacidad():
    with st.expander("🔒 **Aviso de Privacidad Simplificado (Haz clic para leer)**"):
        st.markdown("""
        **EMPODER-ARTE MÉXICO** informa que los datos personales recabados (incluyendo la Clave Única de Registro de Población **CURP** y la fotografía de su identificación oficial **INE**) serán utilizados única y exclusivamente para las siguientes finalidades:
        1. **Verificación de Identidad**: Validar la autenticidad de los perfiles que se integran a la Red Nacional de Emprendedoras para garantizar la seguridad de la comunidad.
        2. **Cifrado de Información**: Sus datos personales sensibles son **encriptados mediante algoritmos criptográficos AES-128 (Fernet)** antes de almacenarse en nuestras bases de datos, evitando cualquier acceso indebido.
        3. **No Transferencia**: Sus datos no serán vendidos, compartidos ni transferidos a ningún tercero ajeno a la administración oficial de la plataforma.
        """)

# Inicialización de usuarios base y verificación de sesión diaria
inicializar_usuarios_base()
sesion_activa_hoy = validar_sesion_diaria()

# Inicializa el esquema SQLite y asegura la cuenta admin fundadora (idempotente).
# Guard por sesión para no reabrir la conexión en cada rerun. Va ANTES del init de
# session_state y ANTES de st.set_page_config (no emite UI, solo SQL). No mover set_page_config.
# NOTA (limitación aceptada): rol_usuario se cachea en login; cambiar/vencer un VIP en
# sesión activa no corta los gates por rol_usuario hasta el próximo login (la Zona VIP sí
# refleja el estado en vivo). Alcance mono-usuario, aceptable.
if "db_inicializada" not in st.session_state:
    try:
        db.inicializar_db()
        st.session_state["db_inicializada"] = True
    except Exception as e:
        st.error("No se pudo conectar a la base de datos. Intenta de nuevo en unos momentos.")
        print(f"[inicializar_db] fallo de conexión/inicialización: {e}")
        st.stop()

if "sesion_activa" not in st.session_state:
    if sesion_activa_hoy:
        st.session_state["sesion_activa"] = True
        st.session_state["email_logueado"] = sesion_activa_hoy["email"]
        st.session_state["usuario_logueado"] = sesion_activa_hoy["nombre"]
        st.session_state["rol_usuario"] = sesion_activa_hoy["rol"]
        st.session_state["es_admin"] = (sesion_activa_hoy["email"] == CORREO_ADMIN or sesion_activa_hoy["rol"] == "Admin")
    else:
        st.session_state["sesion_activa"] = False
        st.session_state["usuario_logueado"] = None
        st.session_state["email_logueado"] = None
        st.session_state["rol_usuario"] = "Visitante"
        st.session_state["es_admin"] = False

if "stream_frame_activo" not in st.session_state:
    st.session_state["stream_frame_activo"] = None
if "transmitiendo_ahora" not in st.session_state:
    st.session_state["transmitiendo_ahora"] = False
if "nombre_emisor_live" not in st.session_state:
    st.session_state["nombre_emisor_live"] = "Empoder-Arte Oficial"
if "versiculo_dia" not in st.session_state:
    st.session_state["versiculo_dia"] = random.choice(VERSICULOS_EMPRENDIMIENTO)

df_emprendedoras = cargar_datos()
img_logo = cargar_imagen_segura(LOGO_IMAGEN)

# ---------------------------------------------------------
# 3. ESTILOS VISUALES: MENÚ LATERAL ROSA Y CURSOR DE CORONA 👑
# ---------------------------------------------------------
st.set_page_config(page_title="Empoder-Arte | Red Nacional", page_icon="👑", layout="wide")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700;800&family=Playfair+Display:ital,wght@0,600;0,700;1,400&display=swap');
    * {
        cursor: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 24 24' fill='%23EF289A'><path d='M5 16L3 5l5.5 5L12 4l3.5 6L21 5l-2 11H5zm14 3c0 .6-.4 1-1 1H6c-.6 0-1-.4-1-1v-1h14v1z'/></svg>") 16 16, auto !important;
    }
    button, a, input, select {
        cursor: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 24 24' fill='%23D81B60'><path d='M5 16L3 5l5.5 5L12 4l3.5 6L21 5l-2 11H5zm14 3c0 .6-.4 1-1 1H6c-.6 0-1-.4-1-1v-1h14v1z'/></svg>") 16 16, pointer !important;
    }
    .brand-font {
        font-family: 'Cinzel', 'Playfair Display', Georgia, serif !important;
        letter-spacing: 1.5px;
    }
    .stApp {
        background: linear-gradient(180deg, #FFF0F5 0%, #FAFAFA 100%);
    }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #F8BBD0 0%, #F48FB1 50%, #EF289A 100%) !important;
        color: #FFFFFF !important;
    }
    [data-testid="stSidebar"] * {
        color: #FFFFFF !important;
    }
    [data-testid="stSidebar"] input {
        color: #222222 !important;
        background-color: #FFFFFF !important;
    }
    input, textarea, select, div[data-baseweb="select"] * {
        color: #222222 !important;
        background-color: #FFFFFF !important;
    }
    .banner-rosa {
        background: linear-gradient(135deg, #EF289A 0%, #D81B60 100%);
        padding: 35px 25px;
        border-radius: 20px;
        text-align: center;
        color: white;
        margin-bottom: 25px;
        box-shadow: 0 8px 20px rgba(239, 40, 154, 0.3);
        border: 2px solid #FF80AB;
    }
    .bible-card {
        background-color: #FFFFFF;
        border-left: 6px solid #D81B60;
        padding: 18px 25px;
        border-radius: 12px;
        margin-bottom: 30px;
        font-style: italic;
        color: #333333;
        box-shadow: 0 4px 12px rgba(216, 27, 96, 0.08);
    }
    .card {
        background-color: #FFFFFF;
        padding: 22px;
        border-radius: 16px;
        border: 2px solid #F8BBD0;
        box-shadow: 0 6px 12px rgba(0,0,0,0.05);
        margin-bottom: 22px;
    }
    .profile-img-header {
        width: 85px !important;
        height: 85px !important;
        border-radius: 50% !important;
        object-fit: cover !important;
        border: 3px solid #D81B60 !important;
        margin-right: 15px !important;
        display: inline-block !important;
        box-shadow: 0 4px 8px rgba(0,0,0,0.12) !important;
    }
    .prod-img-card {
        width: 100%;
        height: 180px;
        object-fit: cover;
        border-radius: 12px;
        margin-bottom: 12px;
        border: 1px solid #F8BBD0;
    }
    .stButton>button {
        background: linear-gradient(135deg, #EF289A 0%, #D81B60 100%) !important;
        color: white !important;
        border-radius: 25px !important;
        border: none !important;
        font-weight: bold !important;
        padding: 10px 20px !important;
        box-shadow: 0 4px 10px rgba(216, 27, 96, 0.25) !important;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #F8BBD0;
        padding: 12px;
        border-radius: 16px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 48px;
        background-color: #FFFFFF;
        border-radius: 10px;
        color: #D81B60;
        font-weight: bold;
        border: 1px solid #F48FB1;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #EF289A 0%, #D81B60 100%) !important;
        color: white !important;
        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
    }
    .chat-container {
        background-color: #FFFFFF;
        border: 1.5px solid #F8BBD0;
        border-radius: 12px;
        padding: 15px;
        height: 380px;
        overflow-y: auto;
        margin-bottom: 12px;
    }
    .capacitacion-container {
        background: linear-gradient(135deg, #FFF0F5 0%, #FCE4EC 100%);
        padding: 25px;
        border-radius: 18px;
        border: 2px solid #F8BBD0;
        box-shadow: 0 4px 15px rgba(216, 27, 96, 0.08);
        margin-bottom: 20px;
    }
    .video-card {
        background-color: #FFFFFF;
        padding: 15px;
        border-radius: 12px;
        border-left: 5px solid #EF289A;
        margin-top: 15px;
    }
    </style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 4. HEADER & BARRA LATERAL ROSA CON GESTIÓN DE CUENTAS
# ---------------------------------------------------------
st.markdown("""
    <div class="banner-rosa">
        <h1 class="brand-font" style="color:white; margin:0; font-size: 42px; text-shadow: 2px 2px 4px rgba(0,0,0,0.2);">EMPODER-ARTE</h1>
        <p style="letter-spacing:2.5px; margin-top:10px; font-weight:bold; font-size:15px; color:#FFE0B2;">RED NACIONAL • MÉXICO • COMUNIDAD Y FE</p>
    </div>
""", unsafe_allow_html=True)

v_info = st.session_state["versiculo_dia"]
st.markdown(f"""
    <div class="bible-card">
        📖 <b style="color:#D81B60;">Palabra para Emprender:</b> "{v_info['texto']}" <br>
        <span style="float: right; font-weight: bold; font-size: 13px; color: #D81B60;">— {v_info['cita']}</span>
        <div style="clear: both;"></div>
    </div>
""", unsafe_allow_html=True)

# BARRA LATERAL (SIDEBAR ROSA)
with st.sidebar:
    if img_logo:
        st.image(img_logo, use_container_width=True)
    else:
        st.markdown('<h2 class="brand-font" style="text-align:center; color:white;">👑 Empoder-Arte</h2>', unsafe_allow_html=True)
        
    st.write("---")
    
    if st.session_state["sesion_activa"]:
        st.success(f"👤 Sesión Activa de Hoy:\n**{st.session_state['usuario_logueado']}**\n\nRol: {st.session_state['rol_usuario']}")
        if st.button("🚪 Cerrar Sesión"):
            cerrar_sesion_local()
            st.session_state["sesion_activa"] = False
            st.session_state["es_admin"] = False
            st.session_state["email_logueado"] = None
            st.session_state["usuario_logueado"] = None
            st.session_state["rol_usuario"] = "Visitante"
            st.rerun()
    else:
        st.info("👋 Modo Visitante. Inicia sesión una vez al día para acceder a tu panel completo.")
        with st.popover("🔑 Iniciar Sesión Persistente"):
            with st.form("form_login_sidebar"):
                email_in = st.text_input("Correo electrónico:").strip().lower()
                pass_in = st.text_input("Contraseña:", type="password").strip()
                btn_in = st.form_submit_button("Ingresar y Recordar Hoy ✨")
                
                if btn_in and email_in and pass_in:
                    # --- Fuente de verdad: validar PRIMERO contra SQLite ---
                    usuario_sql = db.verificar_credenciales(email_in, pass_in)
                    if usuario_sql:
                        # Rama SQLite: fija LAS 5 claves de session_state sin excepción.
                        tipo = usuario_sql["tipo_usuario"]
                        if tipo == "admin":
                            rol = "Admin"
                        elif tipo == "emprendedora":
                            # VIP si la suscripción está vigente; si no, Emprendedora Gratis.
                            rol = "VIP" if db.tiene_acceso_vip(email_in) else "Emprendedora Gratis"
                        elif tipo == "cliente":
                            rol = "Cliente"
                        else:
                            rol = "Visitante"  # defensivo: tipo inesperado NO otorga privilegios
                        st.session_state["sesion_activa"] = True
                        st.session_state["email_logueado"] = email_in
                        st.session_state["usuario_logueado"] = usuario_sql["nombre"]
                        st.session_state["rol_usuario"] = rol
                        st.session_state["es_admin"] = (tipo == "admin")
                        guardar_sesion_diaria(email_in, usuario_sql["nombre"], rol)
                        st.success(f"¡Bienvenida de nuevo, {usuario_sql['nombre']}!")
                        st.rerun()
                    else:
                        # --- Fallback: usuarios.json (bloque legacy intacto) ---
                        hash_ingresado = generar_hash(pass_in)
                        usuarios_db = cargar_usuarios_db()
                        
                        es_fundadora_pass = (email_in == CORREO_ADMIN and pass_in == PASS_ADMIN_PLANA)
                        
                        if email_in in usuarios_db:
                            usr_data = usuarios_db[email_in]
                            if not usr_data.get("activo", True):
                                st.error("⚠️ Tu cuenta ha sido dada de baja por la administración.")
                            elif usr_data["password_hash"] == hash_ingresado or es_fundadora_pass:
                                st.session_state["sesion_activa"] = True
                                st.session_state["email_logueado"] = email_in
                                st.session_state["usuario_logueado"] = usr_data["nombre"]
                                st.session_state["rol_usuario"] = usr_data["rol"]
                                st.session_state["es_admin"] = (usr_data["rol"] == "Admin" or email_in == CORREO_ADMIN)
                                
                                guardar_sesion_diaria(email_in, usr_data["nombre"], usr_data["rol"])
                                st.success(f"¡Bienvenida de nuevo, {usr_data['nombre']}!")
                                st.rerun()
                            else:
                                st.error("Contraseña incorrecta.")
                        else:
                            st.error("Usuario no registrado.")

    st.write("---")
    st.markdown("<h4 style='color:white;' class='brand-font'>⚙️ Herramientas Fundadora</h4>", unsafe_allow_html=True)

    # 1. REGISTRO USUARIO VIP GRATIS
    with st.popover("⭐ Registro VIP Directo (Sin Pago)"):
        st.markdown("<b style='color:#D81B60;'>Alta de Usuario VIP Gratis</b>", unsafe_allow_html=True)
        with st.form("form_alta_vip_directa"):
            nom_vip_s = st.text_input("Nombre Completo")
            email_vip_s = st.text_input("Correo Electrónico").strip().lower()
            pass_vip_s = st.text_input("Contraseña Inicial", type="password")
            btn_crear_vip_s = st.form_submit_button("✨ Otorgar Acceso VIP Gratis")

            if btn_crear_vip_s and nom_vip_s and email_vip_s and pass_vip_s:
                # SQLite es la fuente de verdad: registrar PRIMERO (plan VIP activo).
                resultado_sql = db.registrar_usuario(
                    nombre=nom_vip_s, email=email_vip_s, password=pass_vip_s,
                    tipo_usuario="emprendedora", plan="VIP",
                )
                if not resultado_sql["ok"]:
                    st.error(resultado_sql["mensaje"])  # sin st.stop(): no cortar el render del sidebar
                else:
                    db_usr = cargar_usuarios_db()
                    db_usr[email_vip_s] = {
                        "nombre": nom_vip_s,
                        "password_hash": generar_hash(pass_vip_s),
                        "rol": "VIP",
                        "activo": True
                    }
                    guardar_usuarios_db(db_usr)

                    lat, lon = COORDENADAS_ESTADOS["Querétaro"]
                    df_e = cargar_datos()
                    if df_e[df_e["Email"] == email_vip_s].empty:
                        nueva_u = pd.DataFrame([{
                            "Email": email_vip_s, "Celular": "No especificado", "Nombre": nom_vip_s, "Negocio": "Emprendimiento VIP",
                            "Tipo_Oferta": "Servicios", "Categoria": "Consultoría y Asesoría", "Estado": "Querétaro",
                            "Ciudad": "Querétaro", "Colonia": "Centro", "Contacto": email_vip_s,
                            "Descripcion": "Emprendedora VIP de la red", "Historia": "Miembro destacado.", "Estado_Pago": "VIP",
                            "Metodo_Pago": "Beca Fundadora", "Estado_Aprobacion": "Aprobado",
                            "Foto_Perfil": FOTO_DEFAULT, "INE_Doc": cifrar_dato("Validado"), "CURP_Valor": cifrar_dato("N/A"),
                            "lat": lat, "lon": lon
                        }])
                        df_e = pd.concat([df_e, nueva_u], ignore_index=True)
                        guardar_datos(df_e, ARCHIVO_CSV)

                    st.success(f"¡Usuario VIP {nom_vip_s} creado exitosamente!")
                    st.rerun()

    # 2. RESETEAR CONTRASEÑA RÁPIDA
    with st.popover("🔑 Resetear Contraseña"):
        st.markdown("<b style='color:#D81B60;'>Cambio Rápido de Contraseña</b>", unsafe_allow_html=True)
        db_usr_reset = cargar_usuarios_db()
        if not db_usr_reset:
            st.write("No hay usuarios registrados.")
        else:
            usr_r_sel = st.selectbox("Selecciona cuenta:", list(db_usr_reset.keys()), key="side_usr_reset")
            pass_r_new = st.text_input("Nueva contraseña:", type="password", key="side_pass_reset")
            if st.button("💾 Actualizar Contraseña", key="btn_side_pass_reset"):
                if pass_r_new:
                    db_usr_reset[usr_r_sel]["password_hash"] = generar_hash(pass_r_new)
                    guardar_usuarios_db(db_usr_reset)
                    st.success("¡Contraseña actualizada correctamente!")
                else:
                    st.error("Ingresa una contraseña válida.")

    # 3. ELIMINAR / DAR DE BAJA USUARIO
    with st.popover("❌ Eliminar / Dar de Baja Usuario"):
        st.markdown("<b style='color:#D81B60;'>Eliminación Definitiva de Cuenta</b>", unsafe_allow_html=True)
        db_usr_del = cargar_usuarios_db()
        if not db_usr_del:
            st.write("No hay usuarios registrados.")
        else:
            usr_d_sel = st.selectbox("Selecciona cuenta a eliminar:", list(db_usr_del.keys()), key="side_usr_del")
            if st.button("🔥 Eliminar Cuentas y Registros", key="btn_side_usr_del"):
                eliminar_usuario_definitivo(usr_d_sel)
                st.success(f"El usuario {usr_d_sel} ha sido eliminado definitivamente.")
                st.rerun()

# ---------------------------------------------------------
# 5. PESTAÑAS PRINCIPALES
# ---------------------------------------------------------
titulos_pestañas = [
    "🌸 Directorio de Servicios",
    "🛍️ Marketplace",
    "🗺️ Mapa México",
    "🔴 Transmisión En Vivo",
    "📝 Registro / Unirme",
    "🙏 Petición Oración",
    "💼 Mi Oficina",
    "📚 Educación",
]
# Zona VIP: índice 8 fijo, SIEMPRE presente (antes del Dashboard Admin condicional).
titulos_pestañas.append("👑 Zona VIP / Exclusivo")
if st.session_state["es_admin"]:
    titulos_pestañas.append("📊 Dashboard Admin")  # ahora índice 9 (solo admin)

# ---------------------------------------------------------
# BANNER PUBLICITARIO DE ENTRADA (visible para TODAS las visitantes)
# Se renderiza después del versículo y antes de las pestañas principales.
# ---------------------------------------------------------
try:
    anuncios_vigentes = db.obtener_anuncios_vigentes()
except Exception:
    # Si la BD falla al leer anuncios, no romper la portada: simplemente no mostrar banner.
    anuncios_vigentes = []

if anuncios_vigentes:
    # ROTACIÓN por índice temporal: rota cada minuto para dar exposición equitativa
    # a cada anunciante en cada carga de la portada.
    idx_anuncio = int(time.time() // 60) % len(anuncios_vigentes)
    anuncio_actual = anuncios_vigentes[idx_anuncio]

    titulo_anuncio = anuncio_actual.get("titulo") or ""
    anunciante_anuncio = anuncio_actual.get("anunciante") or ""
    tipo_anuncio = anuncio_actual.get("tipo") or ""
    contenido_anuncio = anuncio_actual.get("contenido") or ""

    # Encabezado rosa coherente con la marca (gradiente 135deg #EF289A -> #D81B60).
    # Banner GRANDE y vistoso: a todo el ancho, encabezado alto y tipografía mayor.
    sub_anunciante = f" · {anunciante_anuncio}" if anunciante_anuncio else ""
    st.markdown(f"""
        <div style="background: linear-gradient(135deg, #EF289A 0%, #D81B60 100%);
                    padding: 34px 32px; border-radius: 22px; margin-bottom: 20px;
                    border: 3px solid #FFFFFF;
                    box-shadow: 0 12px 32px rgba(216, 27, 96, 0.38);">
            <p style="color:#FFE0B2; margin:0 0 6px 0; font-size:14px; font-weight:bold;
                      letter-spacing:3px;">★ PUBLICIDAD{sub_anunciante} ★</p>
            <h2 class="brand-font" style="color:white; margin:0; font-size:40px; line-height:1.1;
                       text-shadow: 2px 2px 5px rgba(0,0,0,0.28);">📢 {titulo_anuncio}</h2>
        </div>
    """, unsafe_allow_html=True)

    if tipo_anuncio == "imagen" and contenido_anuncio:
        # La imagen llega como data URI base64 (data:image/...;base64,...).
        # Banner ancho y alto para máxima visibilidad en la portada.
        st.markdown(
            f'<img src="{contenido_anuncio}" alt="{titulo_anuncio}" '
            'style="width:100%; max-height:620px; object-fit:cover; display:block; '
            'border-radius:20px; margin-bottom:22px; border: 3px solid #F8BBD0; '
            'box-shadow: 0 10px 28px rgba(216, 27, 96, 0.30);">',
            unsafe_allow_html=True,
        )
    elif tipo_anuncio == "video" and contenido_anuncio:
        # Video por URL (YouTube/Vimeo). st.video acepta esas URLs directamente.
        try:
            st.video(contenido_anuncio)
        except Exception:
            # Respaldo responsive por iframe si st.video no pudiera reproducir la URL.
            st.markdown(
                '<div style="position:relative; padding-bottom:56.25%; height:0; '
                'overflow:hidden; border-radius:14px; margin-bottom:16px;">'
                f'<iframe src="{contenido_anuncio}" frameborder="0" allowfullscreen '
                'style="position:absolute; top:0; left:0; width:100%; height:100%;"></iframe>'
                '</div>',
                unsafe_allow_html=True,
            )
        st.markdown('<div style="margin-bottom:16px;"></div>', unsafe_allow_html=True)
elif st.session_state.get("es_admin"):
    # Sin anuncios vigentes: placeholder discreto solo visible para la administradora.
    st.markdown("""
        <div style="border: 3px dashed #EF289A; border-radius: 20px; padding: 40px 24px;
                    margin-bottom: 20px; text-align:center; background-color: #FFF0F5;">
            <div style="font-size:38px; margin-bottom:6px;">📢</div>
            <span style="color:#D81B60; font-weight:bold; font-size:22px;" class="brand-font">
                Espacio publicitario disponible
            </span>
            <p style="color:#D81B60; margin:8px 0 0 0; font-size:16px; font-weight:bold;
                      letter-spacing:1px;">Promociona tu marca aquí · $59 / semana</p>
        </div>
    """, unsafe_allow_html=True)

pestañas = st.tabs(titulos_pestañas)

# --- PESTAÑA 1: DIRECTORIO DE SERVICIOS CON RESEÑAS Y ESTRELLAS ---
with pestañas[0]:
    st.markdown('<h3 class="brand-font" style="color:#D81B60;">🌸 Directorio de Servicios, Historias, Lives y Evaluaciones</h3>', unsafe_allow_html=True)
    df_servicios = df_emprendedoras[
        (df_emprendedoras["Tipo_Oferta"] == "Servicios") & 
        (df_emprendedoras["Estado_Aprobacion"] == "Aprobado")
    ].copy()
    
    df_evals = cargar_evaluaciones()
    df_lives_grab = cargar_lives_grabados()

    if df_servicios.empty:
        st.info("Aún no hay emprendedoras aprobadas en el directorio.")
    else:
        for idx, row in df_servicios.reset_index().iterrows():
            email_emp = row.get('Email', '')
            es_propietaria = st.session_state["sesion_activa"] and ((email_emp == st.session_state["email_logueado"]) or st.session_state["es_admin"])
            es_fundadora = (email_emp == CORREO_ADMIN)
            nombre_mostrar = NOMBRE_FUNDADORA if es_fundadora else row['Nombre']
            contacto_valor = CORREO_ADMIN if es_fundadora else row.get('Contacto', CORREO_ADMIN)
            foto_url_perfil = row.get('Foto_Perfil', FOTO_DEFAULT)
            
            # Calcular calificación promedio de la emprendedora
            evals_perfil = df_evals[df_evals["Email_Destino"] == email_emp]
            if not evals_perfil.empty:
                promedio_estrellas = evals_perfil["Calificacion"].mean()
                total_opiniones = len(evals_perfil)
                estrellas_str = "⭐" * int(round(promedio_estrellas)) + f" ({promedio_estrellas:.1f} / 5.0 - {total_opiniones} opiniones)"
            else:
                estrellas_str = "⭐ Sin calificaciones aún"

            st.markdown(f"""
                <div class="card">
                    <div style="display: flex; align-items: center; margin-bottom: 12px;">
                        <img src="{foto_url_perfil}" class="profile-img-header" alt="Foto de Perfil">
                        <div>
                            <h4 class="brand-font" style="color: #D81B60; margin:0;">💼 {row['Negocio']}</h4>
                            <p style="color: #333; margin:0; font-size:14px;"><b>Por:</b> {nombre_mostrar} | 📧 {email_emp} | 📱 {row.get('Celular','N/A')}</p>
                            <p style="color: #D81B60; margin:0; font-weight:bold; font-size:14px;">{estrellas_str}</p>
                        </div>
                    </div>
                    <p style="color: #555; font-size: 13px;">📍 <b>Ubicación:</b> {row.get('Estado', 'México')} • {row.get('Ciudad', '')} ({row.get('Colonia', '')})</p>
                    <p style="color: #444; font-size: 14px;"><b>Descripción del Servicio:</b> {row['Descripcion']}</p>
                    <div style="background-color: #FFF0F5; padding: 15px; border-radius: 12px; border-left: 5px solid #EF289A; margin-top: 12px;">
                        <b style="color: #D81B60;">📖 Mi Historia Emprendedora:</b><br>
                        <p style="font-style: italic; color: #444; margin-top: 5px;">"{row.get('Historia', 'Aún no ha compartido su historia.')}"</p>
                    </div>
                </div>
            """, unsafe_allow_html=True)

            # LIVES GUARDADOS (DISPONIBLES POR 5 DÍAS)
            lives_e = df_lives_grab[df_lives_grab["Email_Emprendedora"] == email_emp]
            if not lives_e.empty:
                with st.expander(f"🔴 Transmisiones en Vivo Recientes (Disponibles por 5 días) - {row['Negocio']}"):
                    for _, row_l in lives_e.iterrows():
                        st.markdown(f"**🎥 {row_l['Titulo_Live']}** (Emitido: {row_l['Fecha_Emision']})")
                        if row_l["Frame_B64"] != "N/A":
                            st.image(row_l["Frame_B64"], caption="Última captura del Live", use_container_width=True)

            # APARTADO DE EVALUACIÓN Y COMENTARIOS
            with st.expander(f"⭐ Ver Comentarios y Evaluar Perfil ({row['Negocio']})"):
                st.write("<b>Historial de Reseñas:</b>", unsafe_allow_html=True)
                if evals_perfil.empty:
                    st.info("Sé la primera en calificar a esta emprendedora.")
                else:
                    for _, ev_r in evals_perfil.iterrows():
                        st.markdown(f"• **{'⭐' * int(ev_r['Calificacion'])}** - *{ev_r['Autor_Nombre']}*: \"{ev_r['Comentario']}\" ({ev_r['Fecha']})")

                st.write("---")
                if st.session_state["sesion_activa"]:
                    with st.form(f"form_eval_emp_{idx}"):
                        st.write("<b>Deja tu Calificación:</b>", unsafe_allow_html=True)
                        estrellas_input = st.slider("Estrellas (1 a 5)", min_value=1, max_value=5, value=5, key=f"s_est_{idx}")
                        comentario_input = st.text_area("Escribe tu comentario o reseña del servicio:", key=f"s_com_{idx}")
                        btn_calificar = st.form_submit_button("⭐ Publicar Evaluación")

                        if btn_calificar and comentario_input:
                            nueva_eval = pd.DataFrame([{
                                "Fecha": date.today().strftime("%Y-%m-%d"),
                                "Email_Destino": email_emp,
                                "Autor_Email": st.session_state["email_logueado"],
                                "Autor_Nombre": st.session_state["usuario_logueado"],
                                "Calificacion": int(estrellas_input),
                                "Comentario": comentario_input
                            }])
                            df_evals = pd.concat([df_evals, nueva_eval], ignore_index=True)
                            guardar_datos(df_evals, ARCHIVO_EVALUACIONES)
                            st.success("¡Muchas gracias por tu reseña!")
                            st.rerun()
                else:
                    st.info("Inicia sesión para poder calificar y dejar una reseña a esta emprendedora.")

            if es_propietaria:
                curp_descifrada = descifrar_dato(row.get('CURP_Valor', ''))
                with st.expander(f"✏️ Editar Mi Perfil ({row['Negocio']})"):
                    with st.form(f"form_edit_{idx}"):
                        nuevo_nom_neg = st.text_input("Nombre del Negocio", value=row['Negocio'])
                        nuevo_email_e = st.text_input("Correo Electrónico", value=row.get('Email', ''))
                        nuevo_cel_e = st.text_input("Celular / WhatsApp", value=str(row.get('Celular', '')))
                        nueva_curp_e = st.text_input("CURP", value=curp_descifrada)
                        nueva_historia = st.text_area("Mi Historia Emprendedora", value=row.get('Historia', ''))
                        nuevo_est = st.selectbox("Estado", ESTADOS_MEXICO, index=ESTADOS_MEXICO.index(row['Estado']) if row['Estado'] in ESTADOS_MEXICO else 0)
                        nueva_ciud = st.text_input("Ciudad / Municipio", value=row.get('Ciudad', ''))
                        nueva_col = st.text_input("Colonia", value=row.get('Colonia', ''))
                        nuevo_cont = st.text_input("Contacto Público", value=contacto_valor)
                        nueva_desc = st.text_area("Descripción de Oferta", value=row['Descripcion'])
                        
                        st.write("<b>📸 Subir / Cambiar Foto de Perfil:</b>", unsafe_allow_html=True)
                        nueva_foto_edit = st.file_uploader("Seleccionar Imagen para Foto de Perfil", type=["jpg", "png", "jpeg", "webp"], key=f"edit_foto_{idx}")
                        
                        btn_guardar_edit = st.form_submit_button("💾 Guardar Cambios de Perfil")
                        
                        if btn_guardar_edit:
                            lat_e, lon_e = COORDENADAS_ESTADOS.get(nuevo_est, (23.6345, -102.5528))
                            idx_real = row['index'] if 'index' in row else idx
                            
                            df_emprendedoras.loc[idx_real, 'Negocio'] = nuevo_nom_neg
                            df_emprendedoras.loc[idx_real, 'Email'] = nuevo_email_e
                            df_emprendedoras.loc[idx_real, 'Celular'] = nuevo_cel_e
                            df_emprendedoras.loc[idx_real, 'CURP_Valor'] = cifrar_dato(nueva_curp_e)
                            df_emprendedoras.loc[idx_real, 'Historia'] = nueva_historia
                            df_emprendedoras.loc[idx_real, 'Estado'] = nuevo_est
                            df_emprendedoras.loc[idx_real, 'Ciudad'] = nueva_ciud
                            df_emprendedoras.loc[idx_real, 'Colonia'] = nueva_col
                            df_emprendedoras.loc[idx_real, 'Contacto'] = nuevo_cont
                            df_emprendedoras.loc[idx_real, 'Descripcion'] = nueva_desc
                            df_emprendedoras.loc[idx_real, 'lat'] = lat_e
                            df_emprendedoras.loc[idx_real, 'lon'] = lon_e
                            
                            if nueva_foto_edit is not None:
                                df_emprendedoras.loc[idx_real, 'Foto_Perfil'] = convertir_imagen_a_base64(nueva_foto_edit)
                            
                            guardar_datos(df_emprendedoras, ARCHIVO_CSV)
                            st.success("¡Perfil actualizado con éxito!")
                            st.rerun()

# --- PESTAÑA 2: MARKETPLACE CON EDICIÓN Y ELIMINACIÓN DE PUBLICACIONES Y CATEGORÍAS DINÁMICAS ---
with pestañas[1]:
    st.markdown('<h3 class="brand-font" style="color:#D81B60;">🛍️ Marketplace Nacional Empoder-Arte</h3>', unsafe_allow_html=True)
    df_prods_todos = cargar_productos()
    cats_db = cargar_categorias_db()
    lista_prods_cats = cats_db.get("productos", CATEGORIAS_PRODUCTOS_BASE)
    
    if st.session_state["sesion_activa"] and (st.session_state["rol_usuario"] in ["VIP", "Emprendedora Gratis", "Admin", "Administradora"]):
        with st.expander("➕ DAR DE ALTA UN PRODUCTO (EXCLUSIVO EMPRENDEDORAS)"):
            with st.form("form_nuevo_prod_market"):
                prod_nombre = st.text_input("Nombre del Producto")
                prod_precio = st.number_input("Precio ($ MXN)", min_value=1.0, value=100.0, step=10.0)
                
                # LISTA DESPLEGABLE CON OPCIÓN DE AGREGAR MANUALLY
                opciones_cat_p = lista_prods_cats + ["➕ Agregar nueva categoría..."]
                prod_cat_sel = st.selectbox("Categoría", opciones_cat_p)
                prod_cat_nueva = ""
                if prod_cat_sel == "➕ Agregar nueva categoría...":
                    prod_cat_nueva = st.text_input("Escribe el nombre de la nueva categoría:")

                prod_estado = st.selectbox("Estado de Envío / Ubicación", ESTADOS_MEXICO)
                prod_stock = st.number_input("Unidades en Stock", min_value=1, value=5, step=1)
                
                st.write("<b>📸 Foto del Producto:</b>", unsafe_allow_html=True)
                foto_prod_file = st.file_uploader("Subir Imagen del Producto", type=["jpg", "png", "jpeg", "webp"], key="p_foto_new")
                
                btn_crear_prod = st.form_submit_button("🚀 Enviar Publicación a Revisión")
                
                if btn_crear_prod and prod_nombre:
                    cat_final_p = prod_cat_nueva.strip() if prod_cat_sel == "➕ Agregar nueva categoría..." and prod_cat_nueva.strip() else prod_cat_sel
                    if prod_cat_sel == "➕ Agregar nueva categoría..." and prod_cat_nueva.strip():
                        agregar_categoria_dinamica("productos", cat_final_p)

                    estado_ap = "Aprobado" if st.session_state["es_admin"] else "Pendiente"
                    foto_p_base64 = convertir_imagen_a_base64(foto_prod_file) if foto_prod_file else "https://picsum.photos/300/200"
                    
                    nuevo_p_df = pd.DataFrame([{
                        "Email_Emprendedora": st.session_state["email_logueado"],
                        "Producto": prod_nombre,
                        "Precio": float(prod_precio),
                        "Categoria": cat_final_p,
                        "Estado": prod_estado,
                        "Stock": int(prod_stock),
                        "Estado_Aprobacion": estado_ap,
                        "Foto_Producto": foto_p_base64
                    }])
                    df_prods_todos = pd.concat([df_prods_todos, nuevo_p_df], ignore_index=True)
                    guardar_datos(df_prods_todos, ARCHIVO_PRODUCTOS)
                    if estado_ap == "Aprobado":
                        st.success("¡Producto publicado en el Marketplace!")
                    else:
                        st.info("¡Producto registrado! Quedó en revisión para aprobación de la Fundadora.")
                    st.rerun()
    elif not st.session_state["sesion_activa"]:
        st.info("💡 ¿Eres emprendedora de la red? Inicia sesión en la barra lateral para dar de alta tus productos.")
    st.write("---")
    
    st.markdown('<h4 class="brand-font" style="color:#D81B60;">🔎 Buscador de Productos Nacionales</h4>', unsafe_allow_html=True)
    col_f1, col_f2, col_f3, col_f4 = st.columns([2, 1.5, 1.5, 1.5])
    
    with col_f1:
        filtro_texto = st.text_input("🔍 Buscar por Nombre de Producto:", value="")
    with col_f2:
        filtro_cat = st.selectbox("Categoría:", ["Todas"] + lista_prods_cats)
    with col_f3:
        filtro_est = st.selectbox("Ubicación / Estado:", ["Todos"] + ESTADOS_MEXICO)
    with col_f4:
        precio_max = st.slider("Precio Máximo ($ MXN):", min_value=50, max_value=10000, value=10000, step=50)
    
    df_prods = df_prods_todos[df_prods_todos["Estado_Aprobacion"] == "Aprobado"].copy()
    
    if filtro_texto:
        df_prods = df_prods[df_prods["Producto"].str.contains(filtro_texto, case=False, na=False)]
    if filtro_cat != "Todas":
        df_prods = df_prods[df_prods["Categoria"] == filtro_cat]
    if filtro_est != "Todos":
        df_prods = df_prods[df_prods["Estado"] == filtro_est]
    df_prods = df_prods[df_prods["Precio"] <= precio_max]
    st.write("---")
    
    if df_prods.empty:
        st.info("No se encontraron productos que coincidan con los criterios de búsqueda.")
    else:
        cols = st.columns(3)
        for idx, row in df_prods.reset_index().iterrows():
            email_vendedora = row["Email_Emprendedora"]
            info_emp = df_emprendedoras[df_emprendedoras["Email"] == email_vendedora]
            
            if not info_emp.empty:
                nombre_vendedora = info_emp.iloc[0]["Nombre"]
                cel_vendedora = info_emp.iloc[0]["Celular"]
                estado_vendedora = info_emp.iloc[0]["Estado"]
                foto_perfil_vendedora = info_emp.iloc[0].get("Foto_Perfil", FOTO_DEFAULT)
            else:
                nombre_vendedora = "Emprendedora Empoder-Arte"
                cel_vendedora = "No disponible"
                estado_vendedora = row.get("Estado", "México")
                foto_perfil_vendedora = FOTO_DEFAULT
            
            foto_p_url = row.get("Foto_Producto", "https://picsum.photos/300/200")
            
            es_duena_o_admin = st.session_state["sesion_activa"] and (
                (st.session_state["email_logueado"] == email_vendedora) or 
                st.session_state["es_admin"]
            )

            with cols[idx % 3]:
                st.markdown(f"""
                    <div class="card" style="text-align:center;">
                        <img src="{foto_p_url}" class="prod-img-card" alt="Foto Producto">
                        <h4 class="brand-font" style="color:#D81B60; margin:0;">🛍️ {row['Producto']}</h4>
                        <p style="color:#D81B60; font-weight:bold; font-size:22px; margin:5px 0;">${row['Precio']:,.2f} MXN</p>
                        <span style="background-color:#F8BBD0; color:#D81B60; padding:4px 10px; border-radius:12px; font-size:11px; font-weight:bold;">{row['Categoria']}</span>
                        <hr style="margin: 12px 0; border: 0.5px solid #F8BBD0;">
                        <div style="display: flex; align-items: center; justify-content: center; text-align: left;">
                            <img src="{foto_perfil_vendedora}" class="profile-img-header" style="width:45px !important; height:45px !important;" alt="Vendedora">
                            <div>
                                <p style="margin:0; font-size:12px; color:#333;"><b>Vendedora:</b> {nombre_vendedora}</p>
                                <p style="margin:0; font-size:11px; color:#555;">📱 {cel_vendedora} | 📍 {estado_vendedora}</p>
                                <p style="margin:0; font-size:11px; color:#777;">Stock: <b>{row['Stock']} uds.</b></p>
                            </div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
                
                # BOTONES EXCLUSIVOS DE EDICIÓN Y ELIMINACIÓN PARA PROPIETARIA Y ADMINISTRADORA
                if es_duena_o_admin:
                    col_b_edit, col_b_del = st.columns(2)
                    idx_orig = row["index"] if "index" in row else idx
                    
                    with col_b_edit:
                        with st.popover("✏️ Editar"):
                            st.markdown(f"<b style='color:#D81B60;'>Editar Producto: {row['Producto']}</b>", unsafe_allow_html=True)
                            with st.form(f"form_edit_prod_{idx}"):
                                e_prod_nom = st.text_input("Nombre", value=row['Producto'])
                                e_prod_prec = st.number_input("Precio ($ MXN)", min_value=1.0, value=float(row['Precio']), step=10.0)
                                
                                cat_idx = lista_prods_cats.index(row['Categoria']) if row['Categoria'] in lista_prods_cats else 0
                                e_prod_cat_sel = st.selectbox("Categoría", lista_prods_cats + ["➕ Agregar nueva categoría..."], index=cat_idx)
                                e_prod_cat_nueva = ""
                                if e_prod_cat_sel == "➕ Agregar nueva categoría...":
                                    e_prod_cat_nueva = st.text_input("Nombre de la nueva categoría:")

                                e_prod_est = st.selectbox("Estado", ESTADOS_MEXICO, index=ESTADOS_MEXICO.index(row['Estado']) if row['Estado'] in ESTADOS_MEXICO else 0)
                                e_prod_stock = st.number_input("Stock", min_value=0, value=int(row['Stock']), step=1)
                                e_prod_foto = st.file_uploader("Cambiar Imagen del Producto", type=["jpg", "png", "jpeg", "webp"], key=f"e_foto_p_{idx}")
                                
                                btn_save_p_edit = st.form_submit_button("💾 Guardar Cambios")
                                
                                if btn_save_p_edit:
                                    cat_final_edit = e_prod_cat_nueva.strip() if e_prod_cat_sel == "➕ Agregar nueva categoría..." and e_prod_cat_nueva.strip() else e_prod_cat_sel
                                    if e_prod_cat_sel == "➕ Agregar nueva categoría..." and e_prod_cat_nueva.strip():
                                        agregar_categoria_dinamica("productos", cat_final_edit)

                                    df_prods_todos.loc[idx_orig, "Producto"] = e_prod_nom
                                    df_prods_todos.loc[idx_orig, "Precio"] = float(e_prod_prec)
                                    df_prods_todos.loc[idx_orig, "Categoria"] = cat_final_edit
                                    df_prods_todos.loc[idx_orig, "Estado"] = e_prod_est
                                    df_prods_todos.loc[idx_orig, "Stock"] = int(e_prod_stock)
                                    
                                    if e_prod_foto is not None:
                                        df_prods_todos.loc[idx_orig, "Foto_Producto"] = convertir_imagen_a_base64(e_prod_foto)
                                        
                                    guardar_datos(df_prods_todos, ARCHIVO_PRODUCTOS)
                                    st.success("¡Producto actualizado exitosamente!")
                                    st.rerun()

                    with col_b_del:
                        if st.button("🗑️ Eliminar", key=f"btn_del_prod_{idx}"):
                            df_prods_todos = df_prods_todos.drop(index=idx_orig)
                            guardar_datos(df_prods_todos, ARCHIVO_PRODUCTOS)
                            st.success("¡Publicación eliminada correctamente!")
                            st.rerun()

# --- PESTAÑA 3: MAPA INTERACTIVO NACIONAL ---
with pestañas[2]:
    st.markdown('<h3 class="brand-font" style="color:#D81B60;">🗺️ Ubicación Nacional de Emprendedoras Empoder-Arte</h3>', unsafe_allow_html=True)
    df_mapa = df_emprendedoras[df_emprendedoras["Estado_Aprobacion"] == "Aprobado"].copy()
    
    if not df_mapa.empty:
        np.random.seed(42)
        df_mapa["lat_disp"] = df_mapa["lat"] + np.random.uniform(-0.03, 0.03, size=len(df_mapa))
        df_mapa["lon_disp"] = df_mapa["lon"] + np.random.uniform(-0.03, 0.03, size=len(df_mapa))
        
        capa_puntos_rosa = pdk.Layer(
            "ScatterplotLayer",
            data=df_mapa,
            get_position=["lon_disp", "lat_disp"],
            get_color=[239, 40, 154, 210],
            get_radius=30000,
            pickable=True,
            radius_min_pixels=8,
            radius_max_pixels=25,
        )
        
        vista_mexico = pdk.ViewState(
            latitude=23.6345,
            longitude=-102.5528,
            zoom=4.5,
            pitch=0
        )
        
        tooltip_html = {
            "html": "<b>👑 Negocio:</b> {Negocio}<br/><b>Emprendedora:</b> {Nombre}<br/><b>📍 Estado:</b> {Estado}<br/><b>Oferta:</b> {Tipo_Oferta} ({Categoria})",
            "style": {
                "backgroundColor": "#D81B60",
                "color": "white",
                "fontFamily": "Georgia, serif",
                "borderRadius": "10px",
                "padding": "10px"
            }
        }
        
        mapa_deck = pdk.Deck(
            layers=[capa_puntos_rosa],
            initial_view_state=vista_mexico,
            tooltip=tooltip_html,
            map_style=None
        )
        st.pydeck_chart(mapa_deck)

# --- PESTAÑA 4: TRANSMISIÓN EN VIVO ---
with pestañas[3]:
    st.markdown('<h3 class="brand-font" style="color:#D81B60;">🔴 Sala de Live Stream Nativa Empoder-Arte</h3>', unsafe_allow_html=True)
    
    es_vip_o_admin = st.session_state["sesion_activa"] and (
        st.session_state["rol_usuario"] in ["VIP", "Admin", "Administradora"] or 
        st.session_state["email_logueado"] == CORREO_ADMIN
    )
    
    col_live_main, col_chat_side = st.columns([2.2, 1])
    
    with col_live_main:
        if es_vip_o_admin:
            with st.expander("🎥 PANEL DE CONTROL DE TRANSMISIÓN EN VIVO (EXCLUSIVO VIP)", expanded=True):
                st.write("<b>Presiona para gestionar el estado de tu transmisión en vivo:</b>", unsafe_allow_html=True)
                titulo_live_input = st.text_input("Título de la transmisión:", value="Especial de Emprendimiento")
                
                col_btn_start, col_btn_stop = st.columns(2)
                
                with col_btn_start:
                    if st.button("🔴 EMPEZAR A TRANSMITIR", use_container_width=True):
                        st.session_state["transmitiendo_ahora"] = True
                        st.session_state["nombre_emisor_live"] = st.session_state["usuario_logueado"]
                        st.success("🔴 ¡Transmisión activada correctamente!")
                        st.rerun()
                        
                with col_btn_stop:
                    if st.button("⏹️ PARAR TRANSMISIÓN Y GUARDAR (5 DÍAS)", use_container_width=True):
                        st.session_state["transmitiendo_ahora"] = False
                        
                        # Guardar registro en la base de datos de lives
                        df_lives_l = cargar_lives_grabados()
                        nuevo_live = pd.DataFrame([{
                            "Fecha_Emision": date.today().strftime("%Y-%m-%d"),
                            "Email_Emprendedora": st.session_state["email_logueado"],
                            "Nombre_Emprendedora": st.session_state["usuario_logueado"],
                            "Titulo_Live": titulo_live_input,
                            "Frame_B64": st.session_state.get("stream_frame_activo", "N/A")
                        }])
                        df_lives_l = pd.concat([df_lives_l, nuevo_live], ignore_index=True)
                        guardar_datos(df_lives_l, ARCHIVO_LIVES)
                        
                        st.session_state["stream_frame_activo"] = None
                        st.info("⏹️ Transmisión finalizada. Tu transmisión estará disponible en tu perfil durante 5 días.")
                        st.rerun()
                
                st.write("---")
                
                if st.session_state.get("transmitiendo_ahora"):
                    st.markdown("<b style='color:#D81B60;'>📷 Cámara de Emisión Activa:</b>", unsafe_allow_html=True)
                    cámara_stream = st.camera_input("Transmitir video", key="live_cam_input")
                    
                    if cámara_stream is not None:
                        bytes_cam = cámara_stream.getvalue()
                        img_cam = Image.open(BytesIO(bytes_cam))
                        
                        buffered_cam = BytesIO()
                        img_cam.save(buffered_cam, format="JPEG")
                        b64_cam = base64.b64encode(buffered_cam.getvalue()).decode("utf-8")
                        
                        st.session_state["stream_frame_activo"] = f"data:image/jpeg;base64,{b64_cam}"
                        st.success("✨ Señal capturada y emitida a la comunidad.")
        else:
            if not st.session_state["sesion_activa"]:
                st.info("💡 Solo las Emprendedoras VIP pueden iniciar transmisiones en vivo. ¡Inicia sesión si tienes cuenta VIP!")
            else:
                st.info(f"👤 Hola **{st.session_state['usuario_logueado']}**: Tu nivel actual es **{st.session_state['rol_usuario']}**. La función de transmitir en vivo es exclusiva para miembros VIP.")
        
        st.write("---")
        
        st.markdown("<h4 class='brand-font' style='color:#D81B60;'>📺 Pantalla en Vivo de la Comunidad</h4>", unsafe_allow_html=True)
        
        if st.session_state.get("transmitiendo_ahora") and st.session_state.get("stream_frame_activo"):
            emisor = st.session_state.get("nombre_emisor_live", "Emprendedora VIP")
            st.markdown(f"""
                <div style="background-color: #000000; padding: 15px; border-radius: 16px; text-align: center; border: 3px solid #EF289A;">
                    <div style="background-color: #D81B60; color: white; padding: 5px 15px; border-radius: 20px; display: inline-block; font-weight: bold; font-size: 13px; margin-bottom: 10px;">
                        🔴 TRANSMISIÓN EN VIVO • {emisor}
                    </div>
                    <br>
                    <img src="{st.session_state['stream_frame_activo']}" style="width: 100%; max-height: 480px; object-fit: contain; border-radius: 12px;" alt="Stream en vivo">
                </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
                <div style="background-color: #222222; padding: 60px 20px; border-radius: 16px; text-align: center; border: 2px solid #F8BBD0; color: white;">
                    <h3 class="brand-font" style="color: #FF80AB; margin-bottom: 10px;">📺 En Espera de Transmisión</h3>
                    <p style="color: #CCCCCC; font-size: 14px;">En este momento no hay ninguna Emprendedora VIP transmitiendo en vivo.<br>Utiliza el chat lateral para comunicarte con la comunidad.</p>
                </div>
            """, unsafe_allow_html=True)
    with col_chat_side:
        st.markdown("<h4 class='brand-font' style='color:#D81B60;'>💬 Chat en Vivo</h4>", unsafe_allow_html=True)
        
        df_chat = cargar_chat_live()
        
        chat_html = "<div class='chat-container'>"
        if df_chat.empty:
            chat_html += "<p style='color:#888; font-style:italic;'>Sé la primera en escribir en el chat en vivo...</p>"
        else:
            for _, c_row in df_chat.tail(20).iterrows():
                chat_html += f"<div style='margin-bottom:8px;'><b style='color:#D81B60;'>{c_row['Usuario']}:</b> <span style='color:#333;'>{c_row['Mensaje']}</span> <span style='color:#aaa; font-size:10px;'>({c_row['Hora']})</span></div>"
        chat_html += "</div>"
        
        st.markdown(chat_html, unsafe_allow_html=True)
        
        with st.form("form_chat_live_send", clear_on_submit=True):
            if st.session_state["sesion_activa"]:
                user_name_chat = st.session_state["usuario_logueado"]
            else:
                user_name_chat = "Visitante Empoder-Arte"
                
            msg_in = st.text_input("Escribe tu mensaje aquí:", placeholder="Mensaje público...")
            btn_chat_send = st.form_submit_button("Enviar 💌")
            
            if btn_chat_send and msg_in:
                hora_actual = datetime.now().strftime("%H:%M")
                nuevo_msg = pd.DataFrame([{"Hora": hora_actual, "Usuario": user_name_chat, "Mensaje": msg_in}])
                df_chat = pd.concat([df_chat, nuevo_msg], ignore_index=True)
                guardar_datos(df_chat, ARCHIVO_CHAT)
                st.rerun()

# --- PESTAÑA 5: REGISTRO / UNIRME CON CASILLA OBLIGATORIA DE AVISO DE PRIVACIDAD Y CATEGORÍAS DINÁMICAS ---
with pestañas[4]:
    st.markdown('<h3 class="brand-font" style="color:#D81B60;">📝 Únete a la Comunidad Empoder-Arte</h3>', unsafe_allow_html=True)
    mostrar_aviso_privacidad()
    cats_db = cargar_categorias_db()
    
    tab_reg_c, tab_reg_eg, tab_reg_ev = st.tabs([
        "👤 Registro Cliente Gratis", 
        "🌸 Registro Emprendedora Gratis", 
        "💳 Registro Emprendedora VIP ($99 MXN)"
    ])
    
    # REGISTRO CLIENTE GRATIS
    with tab_reg_c:
        with st.form("form_reg_cliente_public"):
            nom_c = st.text_input("Tu Nombre Completo")
            email_c = st.text_input("Correo Electrónico").strip().lower()
            pass_c = st.text_input("Crea una Contraseña para tu cuenta", type="password")
            cel_c = st.text_input("Número de Celular / WhatsApp")
            curp_c_val = st.text_input("Clave CURP Oficial (18 caracteres)").strip().upper()
            estado_c = st.selectbox("Estado donde te ubicas", ESTADOS_MEXICO)
            
            st.write("<b>📸 Foto de Perfil:</b>", unsafe_allow_html=True)
            foto_c_upload = st.file_uploader("Subir Foto de Perfil", type=["jpg", "png", "jpeg", "webp"], key="c_foto_reg")
            
            st.write("<b>🪪 Documento Oficial INE (Validación de Identidad):</b>", unsafe_allow_html=True)
            ine_c_upload = st.file_uploader("Subir Foto de tu INE (Frente o Reverso)", type=["jpg", "png", "jpeg", "pdf"], key="c_ine_reg")
            
            acepta_privacidad_c = st.checkbox("☑️ Acepto de forma obligatoria el Aviso de Privacidad y el tratamiento cifrado de mi CURP e INE.", key="priv_c")
            btn_reg_c = st.form_submit_button("✨ Registrarme como Cliente Gratis")
            
            if btn_reg_c:
                if not acepta_privacidad_c:
                    st.error("⚠️ Debes aceptar obligatoriamente el Aviso de Privacidad marcando la casilla antes de enviar tu registro.")
                elif not (email_c and pass_c and nom_c and cel_c and curp_c_val):
                    st.error("Por favor completa todos los campos requeridos.")
                else:
                    usuarios_db = cargar_usuarios_db()
                    if email_c in usuarios_db or not df_emprendedoras[df_emprendedoras["Email"] == email_c].empty:
                        st.error("Este correo ya está registrado en la plataforma.")
                    elif len(curp_c_val) != 18:
                        st.error("La CURP debe contener exactamente 18 caracteres.")
                    else:
                        # SQLite PRIMERO (barrera atómica): si falla, abortar sin huérfanos en CSV/JSON.
                        resultado_sql = db.registrar_usuario(
                            nombre=nom_c, email=email_c, password=pass_c,
                            tipo_usuario="cliente", plan="Gratuito",
                        )
                        if not resultado_sql["ok"]:
                            st.error(resultado_sql["mensaje"])
                            st.stop()
                        foto_base64 = convertir_imagen_a_base64(foto_c_upload)
                        ine_status = "Subido / En Revisión" if ine_c_upload is not None else "Pendiente"
                        lat, lon = COORDENADAS_ESTADOS.get(estado_c, (23.6345, -102.5528))
                        
                        curp_encriptada = cifrar_dato(curp_c_val)
                        ine_encriptada = cifrar_dato(ine_status)
                        
                        nueva_row = pd.DataFrame([{
                            "Email": email_c, "Celular": cel_c, "Nombre": nom_c, "Negocio": "Cliente Visitante",
                            "Tipo_Oferta": "Cliente", "Categoria": "General", "Estado": estado_c,
                            "Ciudad": "Por definir", "Colonia": "Por definir", "Contacto": cel_c,
                            "Descripcion": "Cliente de la comunidad", "Historia": "Cliente activa.", "Estado_Pago": "Gratis",
                            "Metodo_Pago": "N/A", "Estado_Aprobacion": "Aprobado",
                            "Foto_Perfil": foto_base64,
                            "INE_Doc": ine_encriptada,
                            "CURP_Valor": curp_encriptada,
                            "lat": lat, "lon": lon
                        }])
                        df_emprendedoras = pd.concat([df_emprendedoras, nueva_row], ignore_index=True)
                        guardar_datos(df_emprendedoras, ARCHIVO_CSV)
                        
                        usuarios_db[email_c] = {
                            "nombre": nom_c,
                            "password_hash": generar_hash(pass_c),
                            "rol": "Cliente",
                            "activo": True
                        }
                        guardar_usuarios_db(usuarios_db)
                        
                        st.session_state["sesion_activa"] = True
                        st.session_state["email_logueado"] = email_c
                        st.session_state["usuario_logueado"] = nom_c
                        st.session_state["rol_usuario"] = "Cliente"
                        guardar_sesion_diaria(email_c, nom_c, "Cliente")
                        
                        st.success("¡Registro e inicio de sesión diario completados!")
                        st.rerun()

    # REGISTRO EMPRENDEDORA GRATIS CON CATEGORÍA MANUALLY
    with tab_reg_eg:
        st.markdown("<b style='color:#D81B60;'>🌸 Registro Gratuito para Emprendedoras (Directorio y Marketplace)</b>", unsafe_allow_html=True)
        tipo_oferta_g = st.radio("¿Qué ofrece tu negocio?", ["Servicios", "Productos"], horizontal=True, key="reg_g_tipo_pub")
        
        cats_disponibles_g = cats_db.get("servicios" if tipo_oferta_g == "Servicios" else "productos", [])
        opciones_cat_g = cats_disponibles_g + ["➕ Agregar nueva categoría..."]
        
        with st.form("form_reg_emp_gratis_pub"):
            categoria_sel_g = st.selectbox("Categoría de tu oferta", opciones_cat_g)
            cat_nueva_g = ""
            if categoria_sel_g == "➕ Agregar nueva categoría...":
                cat_nueva_g = st.text_input("Escribe el nombre de la nueva categoría:")

            email_g = st.text_input("Correo Electrónico").strip().lower()
            pass_g = st.text_input("Crea una Contraseña para tu cuenta", type="password")
            cel_g = st.text_input("Número de Celular / WhatsApp")
            nombre_g = st.text_input("Tu Nombre Completo")
            negocio_g = st.text_input("Nombre de tu Emprendimiento")
            curp_g_val = st.text_input("Clave CURP Oficial (18 caracteres)").strip().upper()
            
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                estado_g = st.selectbox("Estado", ESTADOS_MEXICO, key="e_g_est_pub")
                ciudad_g = st.text_input("Ciudad / Municipio", key="e_g_ciud_pub")
            with col_g2:
                colonia_g = st.text_input("Colonia", key="e_g_col_pub")
                contacto_g = st.text_input("Contacto Público (Teléfono/Correo)", key="e_g_cont_pub")
                
            desc_g = st.text_area("Descripción de lo que ofreces")
            historia_g = st.text_area("Cuéntanos tu Historia Emprendedora")
            
            st.write("<b>📸 Foto de Perfil:</b>", unsafe_allow_html=True)
            foto_g_upload = st.file_uploader("Subir Foto de Perfil", type=["jpg", "png", "jpeg", "webp"], key="g_foto_reg")
            
            st.write("<b>🪪 Documento Oficial INE (Validación de Identidad):</b>", unsafe_allow_html=True)
            ine_g_upload = st.file_uploader("Subir Foto de tu INE (Frente o Reverso)", type=["jpg", "png", "jpeg", "pdf"], key="g_ine_reg")
            
            acepta_privacidad_g = st.checkbox("☑️ Acepto de forma obligatoria el Aviso de Privacidad y el tratamiento cifrado de mi CURP e INE.", key="priv_g")
            btn_reg_g = st.form_submit_button("🌸 Enviar Registro Gratis para Revisión")
            
            if btn_reg_g:
                if not acepta_privacidad_g:
                    st.error("⚠️ Debes aceptar obligatoriamente el Aviso de Privacidad marcando la casilla antes de enviar tu registro.")
                elif not (email_g and pass_g and nombre_g and negocio_g and cel_g and curp_g_val):
                    st.error("Por favor completa todos los campos obligatorios.")
                else:
                    cat_final_g = cat_nueva_g.strip() if categoria_sel_g == "➕ Agregar nueva categoría..." and cat_nueva_g.strip() else categoria_sel_g
                    if categoria_sel_g == "➕ Agregar nueva categoría..." and cat_nueva_g.strip():
                        agregar_categoria_dinamica("servicios" if tipo_oferta_g == "Servicios" else "productos", cat_final_g)

                    usuarios_db = cargar_usuarios_db()
                    if email_g in usuarios_db or not df_emprendedoras[df_emprendedoras["Email"] == email_g].empty:
                        st.error("Este correo ya está registrado.")
                    elif len(curp_g_val) != 18:
                        st.error("La CURP debe contener exactamente 18 caracteres.")
                    else:
                        # SQLite PRIMERO (barrera atómica): si falla, abortar sin huérfanos en CSV/JSON.
                        resultado_sql = db.registrar_usuario(
                            nombre=nombre_g, email=email_g, password=pass_g,
                            tipo_usuario="emprendedora", plan="Gratuito",
                        )
                        if not resultado_sql["ok"]:
                            st.error(resultado_sql["mensaje"])
                            st.stop()
                        foto_base64 = convertir_imagen_a_base64(foto_g_upload)
                        ine_status = "Subido / En Revisión" if ine_g_upload is not None else "Pendiente"
                        estado_registro = "Aprobado" if email_g == CORREO_ADMIN else "Pendiente"
                        lat, lon = COORDENADAS_ESTADOS.get(estado_g, (23.6345, -102.5528))
                        
                        curp_encriptada = cifrar_dato(curp_g_val)
                        ine_encriptada = cifrar_dato(ine_status)
                        
                        nueva_row = pd.DataFrame([{
                            "Email": email_g, "Celular": cel_g, "Nombre": nombre_g, "Negocio": negocio_g,
                            "Tipo_Oferta": tipo_oferta_g, "Categoria": cat_final_g, "Estado": estado_g,
                            "Ciudad": ciudad_g, "Colonia": colonia_g, "Contacto": contacto_g,
                            "Descripcion": desc_g, "Historia": historia_g, "Estado_Pago": "Emprendedora Gratis", "Metodo_Pago": "Gratis",
                            "Estado_Aprobacion": estado_registro,
                            "Foto_Perfil": foto_base64,
                            "INE_Doc": ine_encriptada,
                            "CURP_Valor": curp_encriptada,
                            "lat": lat, "lon": lon
                        }])
                        df_emprendedoras = pd.concat([df_emprendedoras, nueva_row], ignore_index=True)
                        guardar_datos(df_emprendedoras, ARCHIVO_CSV)
                        
                        usuarios_db[email_g] = {
                            "nombre": nombre_g,
                            "password_hash": generar_hash(pass_g),
                            "rol": "Emprendedora Gratis",
                            "activo": True
                        }
                        guardar_usuarios_db(usuarios_db)
                        
                        st.session_state["sesion_activa"] = True
                        st.session_state["email_logueado"] = email_g
                        st.session_state["usuario_logueado"] = nombre_g
                        st.session_state["rol_usuario"] = "Emprendedora Gratis"
                        guardar_sesion_diaria(email_g, nombre_g, "Emprendedora Gratis")
                        
                        st.success("¡Registro enviado y guardado de forma segura!")
                        st.rerun()

    # REGISTRO EMPRENDEDORA VIP CON CATEGORÍA MANUALLY
    with tab_reg_ev:
        st.markdown("<b style='color:#D81B60;'>💳 Registro Emprendedora VIP ($99 MXN/mes) — Acceso Completo + Transmisiones en Vivo</b>", unsafe_allow_html=True)
        tipo_oferta_v = st.radio("¿Qué ofrece tu negocio?", ["Servicios", "Productos"], horizontal=True, key="reg_v_tipo_pub")
        
        cats_disponibles_v = cats_db.get("servicios" if tipo_oferta_v == "Servicios" else "productos", [])
        opciones_cat_v = cats_disponibles_v + ["➕ Agregar nueva categoría..."]

        with st.form("form_reg_emp_vip_pub"):
            categoria_sel_v = st.selectbox("Categoría específica", opciones_cat_v)
            cat_nueva_v = ""
            if categoria_sel_v == "➕ Agregar nueva categoría...":
                cat_nueva_v = st.text_input("Escribe el nombre de la nueva categoría:")

            email_v = st.text_input("Correo Electrónico").strip().lower()
            pass_v = st.text_input("Crea una Contraseña para tu cuenta", type="password")
            cel_v = st.text_input("Número de Celular / WhatsApp")
            nombre_v = st.text_input("Tu Nombre Completo")
            negocio_v = st.text_input("Nombre de tu Emprendimiento")
            curp_v_val = st.text_input("Clave CURP Oficial (18 caracteres)").strip().upper()
            
            col_v1, col_v2 = st.columns(2)
            with col_v1:
                estado_v = st.selectbox("Estado", ESTADOS_MEXICO, key="e_v_est_pub")
                ciudad_v = st.text_input("Ciudad / Municipio", key="e_v_ciud_pub")
            with col_v2:
                colonia_v = st.text_input("Colonia", key="e_v_col_pub")
                contacto_v = st.text_input("Contacto Público (Teléfono/Correo)", key="e_v_cont_pub")
                
            desc_v = st.text_area("Descripción de tu negocio")
            historia_v = st.text_area("Cuéntanos tu Historia Emprendedora")
            metodo_v = st.selectbox("Método de Pago ($99 MXN)", ["Mercado Pago / Tarjeta", "Transferencia SPEI"])
            
            st.write("<b>📸 Foto de Perfil:</b>", unsafe_allow_html=True)
            foto_v_upload = st.file_uploader("Subir Foto de Perfil", type=["jpg", "png", "jpeg", "webp"], key="v_foto_reg")
            
            st.write("<b>🪪 Documento Oficial INE (Validación de Identidad):</b>", unsafe_allow_html=True)
            ine_v_upload = st.file_uploader("Subir Foto de tu INE (Frente o Reverso)", type=["jpg", "png", "jpeg", "pdf"], key="v_ine_reg")
            
            acepta_privacidad_v = st.checkbox("☑️ Acepto de forma obligatoria el Aviso de Privacidad y el tratamiento cifrado de mi CURP e INE.", key="priv_v")
            btn_reg_v = st.form_submit_button("💳 Registrar Emprendimiento VIP ($99 MXN) y Enviar a Revisión")
            
            if btn_reg_v:
                if not acepta_privacidad_v:
                    st.error("⚠️ Debes aceptar obligatoriamente el Aviso de Privacidad marcando la casilla antes de enviar tu registro.")
                elif not (email_v and pass_v and nombre_v and negocio_v and cel_v and curp_v_val):
                    st.error("Por favor completa todos los campos requeridos.")
                else:
                    cat_final_v = cat_nueva_v.strip() if categoria_sel_v == "➕ Agregar nueva categoría..." and cat_nueva_v.strip() else categoria_sel_v
                    if categoria_sel_v == "➕ Agregar nueva categoría..." and cat_nueva_v.strip():
                        agregar_categoria_dinamica("servicios" if tipo_oferta_v == "Servicios" else "productos", cat_final_v)

                    usuarios_db = cargar_usuarios_db()
                    if email_v in usuarios_db or not df_emprendedoras[df_emprendedoras["Email"] == email_v].empty:
                        st.error("Este correo ya está registrado.")
                    elif len(curp_v_val) != 18:
                        st.error("La CURP debe contener exactamente 18 caracteres.")
                    else:
                        # SQLite PRIMERO (barrera atómica): si falla, abortar sin huérfanos en CSV/JSON.
                        resultado_sql = db.registrar_usuario(
                            nombre=nombre_v, email=email_v, password=pass_v,
                            tipo_usuario="emprendedora", plan="VIP",
                        )
                        if not resultado_sql["ok"]:
                            st.error(resultado_sql["mensaje"])
                            st.stop()
                        foto_base64 = convertir_imagen_a_base64(foto_v_upload)
                        ine_status = "Subido / En Revisión" if ine_v_upload is not None else "Pendiente"
                        estado_registro = "Aprobado" if email_v == CORREO_ADMIN else "Pendiente"
                        lat, lon = COORDENADAS_ESTADOS.get(estado_v, (23.6345, -102.5528))
                        
                        curp_encriptada = cifrar_dato(curp_v_val)
                        ine_encriptada = cifrar_dato(ine_status)
                        
                        nueva_row = pd.DataFrame([{
                            "Email": email_v, "Celular": cel_v, "Nombre": nombre_v, "Negocio": negocio_v,
                            "Tipo_Oferta": tipo_oferta_v, "Categoria": cat_final_v, "Estado": estado_v,
                            "Ciudad": ciudad_v, "Colonia": colonia_v, "Contacto": contacto_v,
                            "Descripcion": desc_v, "Historia": historia_v, "Estado_Pago": "VIP", "Metodo_Pago": metodo_v,
                            "Estado_Aprobacion": estado_registro,
                            "Foto_Perfil": foto_base64,
                            "INE_Doc": ine_encriptada,
                            "CURP_Valor": curp_encriptada,
                            "lat": lat, "lon": lon
                        }])
                        df_emprendedoras = pd.concat([df_emprendedoras, nueva_row], ignore_index=True)
                        guardar_datos(df_emprendedoras, ARCHIVO_CSV)
                        
                        usuarios_db[email_v] = {
                            "nombre": nombre_v,
                            "password_hash": generar_hash(pass_v),
                            "rol": "VIP",
                            "activo": True
                        }
                        guardar_usuarios_db(usuarios_db)
                        
                        st.session_state["sesion_activa"] = True
                        st.session_state["email_logueado"] = email_v
                        st.session_state["usuario_logueado"] = nombre_v
                        st.session_state["rol_usuario"] = "VIP"
                        guardar_sesion_diaria(email_v, nombre_v, "VIP")
                        
                        st.success("¡Registro VIP completado e inicio de sesión guardado para el día!")
                        st.rerun()

# --- PESTAÑA 6: PETICIÓN DE ORACIÓN CON ÁREA Y CELULAR DE CONTACTO ---
with pestañas[5]:
    st.markdown('<h3 class="brand-font" style="color:#D81B60;">🙏 Petición Privada u Oración Comunitaria</h3>', unsafe_allow_html=True)
    st.write("Unidas en fe y apoyo mutuo. Escribe tu petición para que nuestra comunidad o el equipo pastoral interceda por ti.")
    
    df_oraciones = cargar_oraciones()
    
    with st.form("form_peticion_oracion", clear_on_submit=True):
        if st.session_state["sesion_activa"]:
            nombre_oracion_def = st.session_state["usuario_logueado"]
            email_oracion_def = st.session_state["email_logueado"]
        else:
            nombre_oracion_def = ""
            email_oracion_def = ""
            
        col_o1, col_o2, col_o3 = st.columns(3)
        with col_o1:
            nom_o = st.text_input("Tu Nombre Completo", value=nombre_oracion_def)
        with col_o2:
            email_o = st.text_input("Correo Electrónico", value=email_oracion_def).strip().lower()
        with col_o3:
            area_o = st.selectbox("Área de la Petición", AREAS_ORACION)

        cel_o = st.text_input("📱 Celular / WhatsApp (Opcional): Si deseas que alguien del equipo te contacte para hablar de Dios y orar contigo.")
        peticion_txt = st.text_area("Escribe tu petición de oración o motivo de intercesión:", placeholder="Comparte tus necesidades, agradecimientos o motivos de oración...")
        es_privada = st.checkbox("🔒 Mantener esta petición 100% privada (solo visible para la Fundadora y equipo intercesor)")
        
        btn_enviar_oracion = st.form_submit_button("🙏 Enviar Petición de Oración")
        
        if btn_enviar_oracion and peticion_txt:
            fecha_hoy = date.today().strftime("%Y-%m-%d")
            priv_val = "Sí" if es_privada else "No"
            
            nueva_o = pd.DataFrame([{
                "Fecha": fecha_hoy,
                "Nombre": nom_o if nom_o else "Anónimo",
                "Email": email_o if email_o else "N/A",
                "Celular": cel_o if cel_o else "No proporcionado",
                "Area": area_o,
                "Peticion": peticion_txt,
                "Privada": priv_val
            }])
            
            df_oraciones = pd.concat([df_oraciones, nueva_o], ignore_index=True)
            guardar_datos(df_oraciones, ARCHIVO_ORACIONES)
            st.success("🙏 ¡Tu petición ha sido recibida! Estaremos orando por ti.")

# --- PESTAÑA 7: MI OFICINA (MÉTRICAS, AGENDA, TAREAS Y ELIMINACIÓN DE TRANSACCIONES) ---
with pestañas[6]:
    st.markdown('<h3 class="brand-font" style="color:#D81B60;">💼 Mi Oficina | Empoder-Arte</h3>', unsafe_allow_html=True)
    
    es_vip = st.session_state["sesion_activa"] and (
        st.session_state["rol_usuario"] in ["VIP", "Admin", "Administradora"] or 
        st.session_state["email_logueado"] == CORREO_ADMIN
    )
    
    if not es_vip:
        st.warning("🔒 Esta sección contiene herramientas avanzadas de gestión, inventario, métricas financieras, agenda y pendientes exclusivas para **Emprendedoras VIP**.")
        st.info("Actualiza tu cuenta a VIP ($99 MXN/mes) para habilitar tu panel administrativo completo.")
    else:
        st.markdown("<p style='color:#555;'>Bienvenida a tu centro de control integral. Gestiona tus finanzas, coordina tus citas de negocio y organiza tus actividades pendientes.</p>", unsafe_allow_html=True)
        
        subtab_finanzas, subtab_agenda, subtab_tareas = st.tabs([
            "📊 Métricas Financieras y Ventas",
            "📅 Agenda de Citas y Cursos",
            "✅ Lista de Pendientes (To-Do)"
        ])
        
        email_actual = st.session_state["email_logueado"]
        
        # --- SUBPESTAÑA 1: FINANZAS, MÉTRICAS Y ELIMINACIÓN DE TRANSACCIONES ---
        with subtab_finanzas:
            df_finanzas = cargar_finanzas()
            df_mis_finanzas = df_finanzas.copy() if st.session_state["es_admin"] else df_finanzas[df_finanzas["Email_Emprendedora"] == email_actual].copy()
            
            with st.expander("➕ REGISTRAR NUEVA TRANSACCIÓN (VENTA / GASTO)"):
                with st.form("form_registro_finanzas"):
                    col_f1, col_f2 = st.columns(2)
                    with col_f1:
                        fecha_t = st.date_input("Fecha", value=date.today(), key="fin_fecha")
                        cliente_t = st.text_input("Cliente / Proveedor", placeholder="Ej. María López")
                        tipo_t = st.selectbox("Tipo de Transacción", ["Ingreso (Venta)", "Egreso (Gasto)"])
                    with col_f2:
                        concepto_t = st.text_input("Concepto / Producto", placeholder="Ej. Servicio de Barbería / Insumos")
                        monto_t = st.number_input("Monto ($ MXN)", min_value=1.0, value=150.0, step=10.0)
                        
                    btn_guardar_t = st.form_submit_button("💾 Registrar Transacción")
                    
                    if btn_guardar_t and concepto_t:
                        nueva_t = pd.DataFrame([{
                            "Fecha": fecha_t.strftime("%Y-%m-%d"),
                            "Email_Emprendedora": email_actual,
                            "Cliente": cliente_t if cliente_t else "General",
                            "Concepto": concepto_t,
                            "Monto": float(monto_t),
                            "Tipo": tipo_t
                        }])
                        df_finanzas = pd.concat([df_finanzas, nueva_t], ignore_index=True)
                        guardar_datos(df_finanzas, ARCHIVO_FINANZAS)
                        st.success("¡Transacción registrada exitosamente!")
                        st.rerun()
            st.write("---")
            
            if df_mis_finanzas.empty:
                st.info("Aún no tienes transacciones registradas. Utiliza el formulario superior para añadir tu primera venta.")
            else:
                df_ingresos = df_mis_finanzas[df_mis_finanzas["Tipo"] == "Ingreso (Venta)"]
                df_egresos = df_mis_finanzas[df_mis_finanzas["Tipo"] == "Egreso (Gasto)"]
                
                total_ingresos = df_ingresos["Monto"].sum() if not df_ingresos.empty else 0.0
                total_egresos = df_egresos["Monto"].sum() if not df_egresos.empty else 0.0
                balance_neto = total_ingresos - total_egresos
                num_ventas = len(df_ingresos)
                ticket_promedio = total_ingresos / num_ventas if num_ventas > 0 else 0.0
                
                st.markdown("<h4 class='brand-font' style='color:#D81B60;'>📊 Indicadores Clave de Desempeño (KPIs)</h4>", unsafe_allow_html=True)
                kpi1, kpi2, kpi3, kpi4 = st.columns(4)
                
                kpi1.metric("Ingresos Totales", f"${total_ingresos:,.2f} MXN")
                kpi2.metric("Egresos Totales", f"${total_egresos:,.2f} MXN")
                kpi3.metric("Ganancia Neta", f"${balance_neto:,.2f} MXN")
                kpi4.metric("Ticket Promedio", f"${ticket_promedio:,.2f} MXN")
                
                st.write("---")
                
                col_tabla, col_grafica = st.columns([1.5, 1])
                
                with col_tabla:
                    st.markdown("<h5 class='brand-font' style='color:#D81B60;'>📋 Historial de Transacciones</h5>", unsafe_allow_html=True)
                    st.dataframe(df_mis_finanzas[["Fecha", "Cliente", "Concepto", "Monto", "Tipo"]], use_container_width=True)
                    
                    # ELIMINAR TRANSACCIONES ESPECÍFICAS
                    with st.expander("🗑️ Eliminar Transacción del Historial"):
                        opciones_t = [f"ID {idx_m}: {row_m['Fecha']} - {row_m['Concepto']} (${row_m['Monto']})" for idx_m, row_m in df_mis_finanzas.iterrows()]
                        t_elim_sel = st.selectbox("Selecciona la transacción a borrar:", opciones_t)
                        if st.button("❌ Confirmar Eliminación de Transacción"):
                            idx_borrar = int(t_elim_sel.split(":")[0].replace("ID ", ""))
                            df_finanzas = df_finanzas.drop(index=idx_borrar)
                            guardar_datos(df_finanzas, ARCHIVO_FINANZAS)
                            st.success("¡Transacción eliminada con éxito!")
                            st.rerun()

                with col_grafica:
                    st.markdown("<h5 class='brand-font' style='color:#D81B60;'>📈 Balance Ingresos vs Egresos</h5>", unsafe_allow_html=True)
                    resumen_df = pd.DataFrame({
                        "Categoría": ["Ingresos", "Egresos"],
                        "Monto": [total_ingresos, total_egresos]
                    })
                    st.bar_chart(resumen_df.set_index("Categoría"))

        # --- SUBPESTAÑA 2: AGENDA DE CITAS Y EVENTOS ---
        with subtab_agenda:
            df_agenda = cargar_agenda()
            df_mi_agenda = df_agenda.copy() if st.session_state["es_admin"] else df_agenda[df_agenda["Email_Emprendedora"] == email_actual].copy()
            
            with st.expander("➕ AGENDAR NUEVO EVENTO / CITA"):
                with st.form("form_nueva_cita"):
                    col_ag1, col_ag2 = st.columns(2)
                    with col_ag1:
                        fecha_ag = st.date_input("Fecha del Evento", value=date.today(), key="ag_fecha")
                        hora_ag = st.time_input("Hora", key="ag_hora")
                        evento_ag = st.text_input("Título / Motivo de la Cita", placeholder="Ej. Servicio Lash Lifting / Sesión de Fotos")
                    with col_ag2:
                        cliente_ag = st.text_input("Cliente / Contacto", placeholder="Ej. Sofía Gómez (5512345678)")
                        notas_ag = st.text_area("Notas Adicionales", placeholder="Ej. Anticipo recibido / Traer material especial")
                        
                    btn_agendar = st.form_submit_button("🗓️ Guardar Cita en Agenda")
                    
                    if btn_agendar and evento_ag:
                        nueva_cita = pd.DataFrame([{
                            "Email_Emprendedora": email_actual,
                            "Fecha": fecha_ag.strftime("%Y-%m-%d"),
                            "Hora": hora_ag.strftime("%H:%M"),
                            "Evento": evento_ag,
                            "Cliente_Contacto": cliente_ag if cliente_ag else "N/A",
                            "Notas": notas_ag if notas_ag else "Sin notas"
                        }])
                        df_agenda = pd.concat([df_agenda, nueva_cita], ignore_index=True)
                        guardar_datos(df_agenda, ARCHIVO_AGENDA)
                        st.success("¡Cita programada con éxito!")
                        st.rerun()
            st.write("---")
            st.markdown("<h4 class='brand-font' style='color:#D81B60;'>📆 Mi Calendario de Citas y Compromisos</h4>", unsafe_allow_html=True)
            
            if df_mi_agenda.empty:
                st.info("No tienes citas agendadas por el momento.")
            else:
                st.dataframe(df_mi_agenda[["Fecha", "Hora", "Evento", "Cliente_Contacto", "Notas"]].sort_values(by=["Fecha", "Hora"]), use_container_width=True)

        # --- SUBPESTAÑA 3: LISTA DE PENDIENTES (TO-DO) ---
        with subtab_tareas:
            df_tareas = cargar_tareas()
            df_mis_tareas = df_tareas.copy() if st.session_state["es_admin"] else df_tareas[df_tareas["Email_Emprendedora"] == email_actual].copy()
            
            with st.expander("➕ AÑADIR NUEVO PENDIENTE"):
                with st.form("form_nueva_tarea"):
                    tarea_txt = st.text_input("Descripción de la Tarea / Pendiente", placeholder="Ej. Comprar insumos de uñas / Hacer corte de caja")
                    prio_txt = st.selectbox("Prioridad", ["Alta 🔥", "Media ⚡", "Baja ☕"])
                    btn_crear_tarea = st.form_submit_button("📌 Agregar Pendiente")
                    
                    if btn_crear_tarea and tarea_txt:
                        nueva_t = pd.DataFrame([{
                            "Email_Emprendedora": email_actual,
                            "Tarea": tarea_txt,
                            "Prioridad": prio_txt,
                            "Estatus": "Pendiente ⏳"
                        }])
                        df_tareas = pd.concat([df_tareas, nueva_t], ignore_index=True)
                        guardar_datos(df_tareas, ARCHIVO_TAREAS)
                        st.success("¡Pendiente agregado!")
                        st.rerun()
            st.write("---")
            st.markdown("<h4 class='brand-font' style='color:#D81B60;'>📋 Lista Activa de Tareas</h4>", unsafe_allow_html=True)
            
            if df_mis_tareas.empty:
                st.info("¡Felicidades! No tienes tareas pendientes.")
            else:
                for idx_t, row_t in df_mis_tareas.iterrows():
                    c_t1, c_t2, c_t3 = st.columns([3, 1, 1])
                    c_t1.write(f"• **{row_t['Tarea']}** ({row_t['Prioridad']})")
                    c_t2.write(f"Estado: *{row_t['Estatus']}*")
                    if c_t3.button("✔ Concluir", key=f"btn_done_{idx_t}"):
                        df_tareas.loc[idx_t, "Estatus"] = "Completado ✅"
                        guardar_datos(df_tareas, ARCHIVO_TAREAS)
                        st.success("¡Tarea actualizada!")
                        st.rerun()

# --- PESTAÑA 8: EDUCACIÓN Y CAPACITACIÓN CON COMPRESIÓN DE VIDEO ---
with pestañas[7]:
    st.markdown("""
        <div class="capacitacion-container">
            <h3 class="brand-font" style="color:#D81B60; margin-top:0;">📚 Centro de Capacitación y Cursos Empoder-Arte</h3>
            <p style="color:#444; font-size:14px;">Subes y gestiona las capacitaciones en video para la red. Los videos son optimizados y comprimidos automáticamente para reducir su tamaño de almacenamiento.</p>
        </div>
    """, unsafe_allow_html=True)
    col_subida, col_gestion = st.columns([1.2, 1])
    with col_subida:
        st.markdown("<h4 class='brand-font' style='color:#D81B60;'>📹 Subir Nuevo Taller / Clase</h4>", unsafe_allow_html=True)
        
        with st.form("form_subir_capacitacion", clear_on_submit=True):
            titulo_video = st.text_input("Título de la Capacitación")
            descripcion_video = st.text_area("Descripción del Contenido")
            categoria_video = st.selectbox("Categoría", ["Finanzas & Costos", "Estrategia Digital", "Desarrollo Personal", "Liderazgo & Fe"])
            archivo_video = st.file_uploader("Selecciona el archivo de video (MP4, MOV, AVI)", type=["mp4", "mov", "avi"])
            
            btn_subir_v = st.form_submit_button("🚀 Subir y Comprimir Video")
            if btn_subir_v and archivo_video and titulo_video:
                os.makedirs("videos_capacitacion", exist_ok=True)
                
                ruta_original = os.path.join("videos_capacitacion", f"temp_{archivo_video.name}")
                ruta_comprimida = os.path.join("videos_capacitacion", f"compressed_{archivo_video.name}")
                
                with open(ruta_original, "wb") as f:
                    f.write(archivo_video.getbuffer())
                
                peso_original_mb = os.path.getsize(ruta_original) / (1024 * 1024)
                st.info(f"📦 Tamaño original: {peso_original_mb:.2f} MB. Comprimiendo video...")
                try:
                    comando = [
                        "ffmpeg", "-y", "-i", ruta_original,
                        "-vcodec", "libx264", "-crf", "28",
                        "-preset", "faster", "-acodec", "aac",
                        ruta_comprimida
                    ]
                    subprocess.run(comando, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    
                    peso_comprimido_mb = os.path.getsize(ruta_comprimida) / (1024 * 1024)
                    st.success(f"✨ ¡Video optimizado con éxito! Nuevo tamaño: {peso_comprimido_mb:.2f} MB (Ahorro del {((peso_original_mb - peso_comprimido_mb)/peso_original_mb)*100:.1f}%)")
                    
                    if os.path.exists(ruta_original):
                        os.remove(ruta_original)
                        
                except Exception:
                    st.warning("⚠️ No se detectó ffmpeg instalado localmente. Se conservará el archivo original con resolución nativa.")
                    os.rename(ruta_original, ruta_comprimida)
                
                st.rerun()
    with col_gestion:
        st.markdown("<h4 class='brand-font' style='color:#D81B60;'>🎓 Catálogo de Videocursos</h4>", unsafe_allow_html=True)
        
        carp_videos = "videos_capacitacion"
        if os.path.exists(carp_videos):
            lista_vids = [f for f in os.listdir(carp_videos) if f.startswith("compressed_")]
            if not lista_vids:
                st.info("Aún no hay videos registrados en la plataforma.")
            else:
                for v_item in lista_vids:
                    st.markdown(f"""
                        <div class="video-card">
                            <b style="color:#D81B60; font-size:16px;">🎥 {v_item.replace('compressed_', '').replace('_', ' ')}</b>
                            <p style="color:#666; font-size:12px; margin: 4px 0;">Estado: Disponible en Servidor Local</p>
                        </div>
                    """, unsafe_allow_html=True)
                    st.video(os.path.join(carp_videos, v_item))
        else:
            st.info("Aún no hay videos registrados en la plataforma.")

# --- PESTAÑA 9: ZONA VIP / EXCLUSIVO (índice 8, siempre presente) ---
with pestañas[8]:
    # Resolver el usuario SQLite UNA sola vez y ramificar en 4 estados.
    if not st.session_state.get("sesion_activa"):
        # ESTADO A — Visitante sin sesión: invitar a iniciar sesión.
        st.markdown(
            "<div style='background:linear-gradient(135deg,#D81B60,#EF289A);padding:28px;"
            "border-radius:16px;text-align:center;color:white;'>"
            "<h2 class='brand-font'>👑 Zona VIP / Exclusivo</h2>"
            "<p>Inicia sesión en la barra lateral para acceder a tu contenido premium.</p>"
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        email = st.session_state.get("email_logueado")
        usuario_sql = db.obtener_usuario_por_email(email) if email else None
        if usuario_sql is None:
            # ESTADO B — cuenta solo en JSON (o email None): NO decir "caducada".
            st.markdown(
                "<div style='background:#FFF0F6;border:2px solid #EF289A;padding:24px;"
                "border-radius:14px;color:#D81B60;'>"
                "<h3 class='brand-font'>👑 Zona VIP / Exclusivo</h3>"
                "<p>Tu cuenta aún no está en el nuevo sistema de suscripciones. "
                "Contacta a la fundadora para activarla.</p></div>",
                unsafe_allow_html=True,
            )
        elif db.tiene_acceso_vip(usuario_sql["id"]):
            # ESTADO C — acceso VIP vigente: contenido premium decorado (placeholder).
            st.markdown(
                "<div style='background:linear-gradient(135deg,#D81B60,#EF289A);padding:28px;"
                "border-radius:16px;color:white;'>"
                "<h2 class='brand-font'>👑 Bienvenida a tu Zona VIP ✨</h2>"
                "<p>Tienes acceso premium activo. Aquí verás tus beneficios exclusivos.</p></div>",
                unsafe_allow_html=True,
            )
            st.success("✨ Tu suscripción VIP está activa.")
            st.markdown("- 🎥 Transmisiones y grabaciones exclusivas\n"
                        "- 📈 Métricas y herramientas de Mi Oficina\n"
                        "- 🛍️ Publicación destacada en el Marketplace")
        else:
            # ESTADO D — existe pero sin acceso (inactivo/pendiente/vencido).
            st.markdown(
                "<div style='background:#FFF0F6;border:2px solid #D81B60;padding:24px;"
                "border-radius:14px;color:#D81B60;text-align:center;'>"
                "<h3 class='brand-font'>⚠️ Tu suscripción VIP ha caducado o está inactiva</h3>"
                "<p>Renueva tu membresía para recuperar el acceso premium.</p></div>",
                unsafe_allow_html=True,
            )
            st.markdown("### 💳 Renovar / Activar VIP")
            if st.button("💳 Simular pago y activar VIP", key="btn_pago_vip_zona"):
                db.activar_suscripcion_vip(usuario_sql["id"])
                st.success("¡Pago simulado! Tu suscripción VIP quedó activa.")
                st.rerun()

# --- PESTAÑA 10: DASHBOARD ADMIN & GESTIÓN TOTAL DE USUARIOS ---
if st.session_state["es_admin"]:
    with pestañas[9]:
        st.markdown('<h3 class="brand-font" style="color:#D81B60;">👑 Módulo Exclusivo de Aprobación, Seguridad y Gestión de Usuarios (Fundadora)</h3>', unsafe_allow_html=True)
        st.write("Bienvenida, Larissa. Desde este panel tienes control total sobre los usuarios, asignación de roles, bajas, eliminación definitiva y reseteo de contraseñas.")
        
        t_admin_ver, t_admin_ctrl, t_admin_new, t_admin_reset, t_admin_del, t_admin_subs, t_admin_pub = st.tabs([
            "🔍 Verificación & Cifrado (CURP/INE)",
            "⚙️ Control de Roles y Bajas",
            "➕ Registrar Usuario VIP / Admin",
            "🔑 Reseteo de Contraseñas",
            "🔥 Eliminación Definitiva",
            "💳 Gestión de Suscripciones",
            "📢 Publicidad / Banners"
        ])
        
        usuarios_db = cargar_usuarios_db()
        
        # SUBPESTAÑA 1: VALIDACIÓN DE IDENTIDAD Y DATOS CIFRADOS
        with t_admin_ver:
            st.markdown("<h4 class='brand-font' style='color:#D81B60;'>📄 Registros y Descifrado de Seguridad</h4>", unsafe_allow_html=True)
            df_admin_ver = df_emprendedoras.copy()
            df_admin_ver["CURP_Descifrada"] = df_admin_ver["CURP_Valor"].apply(descifrar_dato)
            df_admin_ver["INE_Estado"] = df_admin_ver["INE_Doc"].apply(descifrar_dato)
            
            st.dataframe(
                df_admin_ver[["Nombre", "Email", "Negocio", "Estado_Pago", "Estado_Aprobacion", "CURP_Descifrada", "INE_Estado"]],
                use_container_width=True
            )
            
        # SUBPESTAÑA 2: CONTROL DE ROLES Y BAJAS TEMPORALES
        with t_admin_ctrl:
            st.markdown("<h4 class='brand-font' style='color:#D81B60;'>🛡️ Modificar Rol o Estado de Cuenta</h4>", unsafe_allow_html=True)
            if not usuarios_db:
                st.info("No hay usuarios registrados en el sistema.")
            else:
                lista_emails = list(usuarios_db.keys())
                usr_sel = st.selectbox("Selecciona el usuario a gestionar:", lista_emails, key="sel_usr_ctrl")
                
                datos_u = usuarios_db[usr_sel]
                col_c1, col_c2 = st.columns(2)
                
                with col_c1:
                    st.write(f"**Nombre:** {datos_u.get('nombre')}")
                    st.write(f"**Rol Actual:** {datos_u.get('rol')}")
                    st.write(f"**Estatus Cuenta:** {'Activa ✅' if datos_u.get('activo', True) else 'Inactiva / Baja ❌'}")
                    
                with col_c2:
                    nuevo_rol_sel = st.selectbox("Asignar Nuevo Rol:", ["VIP", "Admin", "Emprendedora Gratis", "Cliente"], key="sel_rol_usr")
                    estatus_cuenta = st.radio("Estatus de la Cuenta:", ["Activa", "Dada de Baja"], index=0 if datos_u.get('activo', True) else 1)
                    
                    if st.button("💾 Guardar Cambios de Usuario", key="btn_save_usr_ctrl"):
                        usuarios_db[usr_sel]["rol"] = nuevo_rol_sel
                        usuarios_db[usr_sel]["activo"] = (estatus_cuenta == "Activa")
                        
                        mask_emp = df_emprendedoras["Email"] == usr_sel
                        if mask_emp.any():
                            df_emprendedoras.loc[mask_emp, "Estado_Pago"] = nuevo_rol_sel
                            guardar_datos(df_emprendedoras, ARCHIVO_CSV)
                            
                        guardar_usuarios_db(usuarios_db)
                        st.success(f"¡Usuario {usr_sel} actualizado correctamente!")
                        st.rerun()

        # SUBPESTAÑA 3: ALTA MANUAL DE USUARIOS VIP / ADMIN
        with t_admin_new:
            st.markdown("<h4 class='brand-font' style='color:#D81B60;'>➕ Alta Manual de Usuario VIP o Administrador</h4>", unsafe_allow_html=True)
            with st.form("form_alta_manual_admin"):
                n_nom = st.text_input("Nombre Completo:")
                n_email = st.text_input("Correo Electrónico:").strip().lower()
                n_pass = st.text_input("Contraseña Inicial:", type="password")
                n_rol = st.selectbox("Rol Asignado:", ["VIP", "Admin", "Emprendedora Gratis", "Cliente"])
                
                btn_alta = st.form_submit_button("✨ Registrar Usuario Manualmente")
                
                if btn_alta and n_email and n_pass and n_nom:
                    if n_email in usuarios_db:
                        st.error("El usuario ya existe en la base de datos.")
                    else:
                        usuarios_db[n_email] = {
                            "nombre": n_nom,
                            "password_hash": generar_hash(n_pass),
                            "rol": n_rol,
                            "activo": True
                        }
                        guardar_usuarios_db(usuarios_db)
                        st.success(f"¡Usuario {n_nom} ({n_rol}) creado con éxito!")
                        st.rerun()

        # SUBPESTAÑA 4: FACULTAD DE RESETEAR CONTRASEÑAS
        with t_admin_reset:
            st.markdown("<h4 class='brand-font' style='color:#D81B60;'>🔑 Resetear Contraseña de Usuario</h4>", unsafe_allow_html=True)
            if not usuarios_db:
                st.info("No hay usuarios registrados.")
            else:
                usr_reset = st.selectbox("Selecciona la cuenta a resetear:", list(usuarios_db.keys()), key="sel_usr_reset_tab")
                nueva_pass = st.text_input("Escribe la nueva contraseña:", type="password", key="txt_new_pass_tab")
                
                if st.button("🔑 Cambiar y Resetear Contraseña", key="btn_do_reset_tab"):
                    if nueva_pass:
                        usuarios_db[usr_reset]["password_hash"] = generar_hash(nueva_pass)
                        guardar_usuarios_db(usuarios_db)
                        st.success(f"¡Contraseña del usuario {usr_reset} actualizada exitosamente!")
                    else:
                        st.error("Debes ingresar la nueva contraseña.")

        # SUBPESTAÑA 5: ELIMINACIÓN DEFINITIVA DE CUENTAS
        with t_admin_del:
            st.markdown("<h4 class='brand-font' style='color:#D81B60;'>🔥 Bajas y Eliminación Permanente de Usuarios</h4>", unsafe_allow_html=True)
            if not usuarios_db:
                st.info("No hay usuarios registrados.")
            else:
                usr_del_tab = st.selectbox("Selecciona la cuenta a eliminar definitivamente:", list(usuarios_db.keys()), key="sel_usr_del_tab")
                st.warning(f"⚠️ Atención: Al presionar el botón se eliminará permanentemente la cuenta {usr_del_tab} de 'usuarios.json' y de 'emprendedoras.csv'.")
                
                if st.button("🔥 Confirmar Eliminación Definitiva", key="btn_confirm_del_tab"):
                    eliminar_usuario_definitivo(usr_del_tab)
                    st.success(f"¡El usuario {usr_del_tab} ha sido borrado del sistema!")
                    st.rerun()

        # SUBPESTAÑA 6: GESTIÓN DE SUSCRIPCIONES (SQLite, fuente de verdad VIP)
        with t_admin_subs:
            st.markdown("<h4 class='brand-font' style='color:#D81B60;'>💳 Gestión de Suscripciones</h4>", unsafe_allow_html=True)
            filas = db.listar_usuarios_con_suscripcion()
            if not filas:
                st.info("Aún no hay usuarios en la base de datos SQLite.")
            else:
                st.dataframe(
                    [{"Nombre": f["nombre"], "Email": f["email"], "Tipo": f["tipo_usuario"],
                      "Plan": f["plan"], "Estado": f["estado"], "Vence": f["fecha_vencimiento"]} for f in filas],
                    use_container_width=True,
                )
                # Mapa etiqueta -> usuario_id para seleccionar al usuario.
                opciones_subs = {f"{f['nombre']} <{f['email']}>": f["usuario_id"] for f in filas}
                sel_label = st.selectbox("Selecciona un usuario:", list(opciones_subs.keys()), key="sel_subs_admin")
                usuario_id_sel = opciones_subs[sel_label]

                nuevo_estado = st.selectbox("Nuevo estado:", ("activo", "inactivo", "pendiente"), key="sel_estado_subs")
                if st.button("💾 Actualizar estado", key="btn_act_estado_subs"):
                    if db.actualizar_estado_suscripcion(usuario_id_sel, nuevo_estado):
                        st.success("Estado de suscripción actualizado.")
                        st.rerun()
                    else:
                        st.warning("No se pudo actualizar el estado (sin suscripción o estado inválido).")

                if st.button("👑 Activar VIP directo", key="btn_vip_directo_subs"):
                    if db.activar_suscripcion_vip(usuario_id_sel):
                        st.success("Suscripción VIP activada.")
                        st.rerun()
                    else:
                        st.warning("No se pudo activar el VIP.")

        # SUBPESTAÑA 7: PUBLICIDAD / BANNERS (gestión de anuncios de la portada)
        with t_admin_pub:
            st.markdown("<h4 class='brand-font' style='color:#D81B60;'>📢 Publicidad / Banners de Entrada</h4>", unsafe_allow_html=True)
            st.info("💲 Precio de referencia: **$59/semana** por banner (imagen o video). El cobro se realiza por fuera; aquí programas las fechas y el banner se activa y rota solo.")

            # --- FORMULARIO DE ALTA DE ANUNCIO ---
            with st.form("form_alta_anuncio"):
                an_titulo = st.text_input("Título del anuncio:")
                an_anunciante = st.text_input("Anunciante (opcional):")
                an_tipo = st.radio("Tipo de banner:", ["imagen", "video"], horizontal=True)
                an_foto_file = None
                an_video_url = ""
                if an_tipo == "imagen":
                    an_foto_file = st.file_uploader("Imagen del banner (JPG/PNG):", type=["jpg", "jpeg", "png"], key="file_banner_pub")
                else:
                    an_video_url = st.text_input("URL del video (YouTube/Vimeo):").strip()
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    an_fecha_inicio = st.date_input("Fecha de inicio:", value=date.today(), key="date_ini_banner")
                with col_f2:
                    an_fecha_fin = st.date_input("Fecha de fin:", value=date.today() + timedelta(days=7), key="date_fin_banner")
                btn_crear_anuncio = st.form_submit_button("📢 Programar banner ($59/semana)")

                if btn_crear_anuncio:
                    # Validaciones mínimas antes de insertar en la BD.
                    if not an_titulo:
                        st.error("El título es obligatorio.")
                    elif an_fecha_fin < an_fecha_inicio:
                        st.error("La fecha de fin no puede ser anterior a la de inicio.")
                    else:
                        # Resolver el contenido según el tipo: imagen -> data URI base64; video -> URL.
                        if an_tipo == "imagen":
                            if an_foto_file is None:
                                contenido_nuevo = None
                            else:
                                contenido_nuevo = convertir_imagen_a_base64(an_foto_file)
                        else:
                            contenido_nuevo = an_video_url or None

                        if not contenido_nuevo:
                            st.error("Debes subir una imagen o proporcionar la URL del video.")
                        else:
                            try:
                                db.crear_anuncio(
                                    titulo=an_titulo,
                                    tipo=an_tipo,
                                    contenido=contenido_nuevo,
                                    fecha_inicio=an_fecha_inicio.strftime("%Y-%m-%d"),
                                    fecha_fin=an_fecha_fin.strftime("%Y-%m-%d"),
                                    anunciante=an_anunciante,
                                )
                                st.success("¡Banner programado correctamente!")
                                st.rerun()
                            except Exception as e:
                                st.error("No se pudo guardar el banner. Intenta de nuevo.")
                                print(f"[anuncios] Error al crear anuncio: {e}")

            st.write("---")

            # --- LISTADO DE ANUNCIOS CON ESTADO POR FECHA Y ACCIONES ---
            st.markdown("<h5 class='brand-font' style='color:#D81B60;'>📋 Banners programados</h5>", unsafe_allow_html=True)
            try:
                lista_anuncios = db.listar_anuncios()
            except Exception as e:
                lista_anuncios = []
                st.error("No se pudieron cargar los anuncios.")
                print(f"[anuncios] Error al listar anuncios: {e}")

            if not lista_anuncios:
                st.info("Aún no hay banners programados.")
            else:
                hoy = date.today()
                for an in lista_anuncios:
                    an_id = an.get("id")
                    f_ini = an.get("fecha_inicio")
                    f_fin = an.get("fecha_fin")
                    activo = an.get("activo", True)

                    # Normalizar fechas (llegan como datetime.date desde Postgres).
                    f_ini_d = f_ini if isinstance(f_ini, date) else None
                    f_fin_d = f_fin if isinstance(f_fin, date) else None

                    # Estado calculado por la fecha de HOY.
                    if not activo:
                        estado_txt = "⛔ Inactivo"
                    elif f_ini_d and hoy < f_ini_d:
                        estado_txt = "🗓️ Programado"
                    elif f_fin_d and hoy > f_fin_d:
                        estado_txt = "⌛ Vencido"
                    else:
                        estado_txt = "✅ Vigente"

                    with st.container():
                        st.markdown(
                            f"**{an.get('titulo', '(sin título)')}** · _{an.get('tipo', '')}_"
                            f"{(' · ' + an.get('anunciante')) if an.get('anunciante') else ''}"
                        )
                        st.caption(
                            f"Vigencia: {f_ini_d or f_ini} → {f_fin_d or f_fin}  |  Estado: {estado_txt}  |  $59/semana"
                        )
                        col_a1, col_a2, col_a3 = st.columns(3)
                        with col_a1:
                            if activo:
                                if st.button("⏸️ Desactivar", key=f"btn_desact_an_{an_id}"):
                                    db.activar_desactivar_anuncio(an_id, False)
                                    st.rerun()
                            else:
                                if st.button("▶️ Activar", key=f"btn_act_an_{an_id}"):
                                    db.activar_desactivar_anuncio(an_id, True)
                                    st.rerun()
                        with col_a3:
                            if st.button("🗑️ Eliminar", key=f"btn_del_an_{an_id}"):
                                db.eliminar_anuncio(an_id)
                                st.rerun()
                        st.write("---")

                    # =============================================================================
# MÓDULO DE CONTROL DE SUSCRIPCIONES Y BLOQUEO DE FUNCIONALIDADES VIP (30 DÍAS)
# =============================================================================

def verificar_estatus_suscripcion_vip(email: str) -> tuple[bool, str, int]:
    """
    Verifica si la suscripción VIP del usuario está vigente.
    - Tarjeta / Mercado Pago: Domiciliación automática (siempre activo).
    - Transferencia SPEI: Vigencia estricta de 30 días.
    Retorna: (es_vip_activo, mensaje_alerta, dias_restantes)
    """
    if email == CORREO_ADMIN:
        return True, "Suscripción Administradora Activa permanentemente.", 365
    
    db_u = cargar_usuarios_db()
    if email not in db_u:
        return False, "Usuario no registrado.", 0
    
    usr = db_u[email]
    if usr.get("rol") != "VIP":
        return False, "Usuario con perfil gratuito.", 0
    
    metodo = usr.get("metodo_pago", "Transferencia SPEI")
    
    # Si la tarjeta está domiciliada (Mercado Pago / Tarjeta)
    if "Tarjeta" in metodo or "Mercado Pago" in metodo or "Domiciliada" in metodo:
        return True, "Suscripción VIP activa mediante cobro domiciliado.", 30
    
    # Si el pago es por SPEI / Transferencia
    fecha_reg_str = usr.get("fecha_registro", date.today().strftime("%Y-%m-%d"))
    try:
        fecha_reg = datetime.strptime(fecha_reg_str, "%Y-%m-%d").date()
    except Exception:
        fecha_reg = date.today()
        
    dias_transcurridos = (date.today() - fecha_reg).days
    dias_restantes = 30 - dias_transcurridos
    
    if dias_restantes <= 0:
        return False, "⚠️ Tu suscripción VIP por SPEI ha vencido. Realiza tu pago de renovación ($99 MXN) para desbloquear tus beneficios.", 0
    elif dias_restantes <= 5:
        return True, f"⏰ Recordatorio: Quedan {dias_restantes} días para el vencimiento de tu suscripción VIP. Realiza tu renovación por SPEI.", dias_restantes
    
    return True, f"Suscripción VIP activa ({dias_restantes} días restantes).", dias_restantes


def renderizar_alertas_y_control_vip():
    """
    Renderiza los mensajes de advertencia de renovación por SPEI y aplica
    el bloqueo de seguridad a todas las secciones VIP si la suscripción venció.
    """
    if not st.session_state.get("sesion_activa"):
        return
    
    email_user = st.session_state.get("email_logueado")
    rol_user = st.session_state.get("rol_usuario")
    
    if rol_user == "VIP":
        es_activo, mensaje, dias_r = verificar_estatus_suscripcion_vip(email_user)
        
        # Muestra de alertas visuales en la parte superior
        if not es_activo:
            st.error(f"🔴 **Suscripción VIP Inactiva:** {mensaje}")
            st.info("💡 **Cuenta restringida a funciones gratuitas:** Se han bloqueado tus herramientas avanzadas (Live Stream, Métricas Financieras, Agenda y Publicaciones Directas en Marketplace) hasta registrar tu pago de $99 MXN.")
        elif dias_r <= 5 and "⏰" in mensaje:
            st.warning(f"🟡 **Aviso de Renovación Próxima:** {mensaje}")

# Control VIP legacy JSON DESHABILITADO: SQLite (database.py) es la ÚNICA fuente de verdad
# de suscripciones. Ver Zona VIP (pestañas[8]) y Gestión de Suscripciones (t_admin_subs).
# Las funciones se dejan definidas (sin invocar) para facilitar rollback.
# renderizar_alertas_y_control_vip()