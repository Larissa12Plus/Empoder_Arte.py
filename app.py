import streamlit as st
import pandas as pd
import numpy as np
import os
import base64
from io import BytesIO
from datetime import date
from PIL import Image

# ---------------------------------------------------------
# 1. CONFIGURACIÓN DE BASES DE DATOS Y COORDENADAS
# ---------------------------------------------------------
CARPETA_PROYECTO = "app_empoder_arte"
ARCHIVO_CSV = "emprendedoras.csv"
ARCHIVO_CHAT = "chat_live.csv"
ARCHIVO_FINANZAS = "finanzas.csv"
ARCHIVO_CLIENTES = "clientes.csv"
ARCHIVO_PRODUCTOS = "productos.csv"
ARCHIVO_ORACIONES = "oraciones.csv"
CORREO_ADMIN = "garcialarissa1292@gmail.com"
NOMBRE_FUNDADORA = "Larissa García"
LOGO_IMAGEN = "Empoder Arte Order_blanco_2.png"

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
    "Yucatán": (20.9674, -89.5926), "Zacatecas": (22.7709, -102.5832)
}

VERSICULOS_EMPRENDIMIENTO = [
    {"texto": "Ella hace telas de lino y las vende, y provee cinturones a los comerciantes. Fuerza y dignidad son su vestidura.", "cita": "Proverbios 31:24-25"},
    {"texto": "Considera la compra de un campo y lo compra; con el fruto de sus manos planta una viña.", "cita": "Proverbios 31:16"},
    {"texto": "Encomienda al Señor tus obras, y tus pensamientos serán afirmados.", "cita": "Proverbios 16:3"},
    {"texto": "Y todo lo que hagáis, hacedlo de corazón, como para el Señor y no para los hombres.", "cita": "Colosenses 3:23"},
    {"texto": "Porque Dios no nos ha dado un espíritu de timidez, sino de poder, de amor y de dominio propio.", "cita": "2 Timoteo 1:7"}
]

LISTA_SERVICIOS = ["Belleza y Estética", "Diseño y Creatividad", "Consultoría y Asesoría", "Eventos y Fotografía", "Reparaciones y Confección", "Educación y Clases", "Otro Servicio"]
LISTA_PRODUCTOS = ["Postres y Repostería", "Cuidado Personal y Cosmética", "Moda y Accesorios", "Decoración y Hogar", "Papelería y Agendas", "Artesanías y Manualidades", "Otro Producto"]

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
            image = Image.open(uploaded_file)
            buffered = BytesIO()
            image.convert("RGB").save(buffered, format="JPEG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            return f"data:image/jpeg;base64,{img_str}"
        except Exception:
            return "https://via.placeholder.com/150"
    return "https://via.placeholder.com/150"

def crear_df_inicial_fundadora():
    lat, lon = COORDENADAS_ESTADOS["Querétaro"]
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
        "Foto_Perfil": "https://via.placeholder.com/150",
        "INE_Doc": "Validado",
        "CURP_Valor": "GAGL921211XXXXXX00",
        "lat": lat,
        "lon": lon
    }])

def cargar_datos():
    if os.path.exists(ARCHIVO_CSV):
        try:
            df = pd.read_csv(ARCHIVO_CSV)
            if df.empty:
                df = crear_df_inicial_fundadora()
                df.to_csv(ARCHIVO_CSV, index=False)
            else:
                for col in ["Estado", "Ciudad", "Colonia", "Tipo_Oferta", "Estado_Aprobacion", "Celular", "Foto_Perfil", "INE_Doc", "CURP_Valor", "Historia"]:
                    if col not in df.columns:
                        df[col] = "Querétaro" if col == "Estado" else ("Aprobado" if col == "Estado_Aprobacion" else ("https://via.placeholder.com/150" if col == "Foto_Perfil" else "Por definir"))
                if "lat" not in df.columns or "lon" not in df.columns:
                    df["lat"] = df["Estado"].map(lambda x: COORDENADAS_ESTADOS.get(x, (23.6345, -102.5528))[0])
                    df["lon"] = df["Estado"].map(lambda x: COORDENADAS_ESTADOS.get(x, (23.6345, -102.5528))[1])
                mask_admin = df["Email"] == CORREO_ADMIN
                if mask_admin.any():
                    df.loc[mask_admin, "Nombre"] = NOMBRE_FUNDADORA
                    df.loc[mask_admin, "Estado_Aprobacion"] = "Aprobado"
                    df.to_csv(ARCHIVO_CSV, index=False)
            return df
        except Exception:
            df_i = crear_df_inicial_fundadora()
            df_i.to_csv(ARCHIVO_CSV, index=False)
            return df_i
    else:
        df_i = crear_df_inicial_fundadora()
        df_i.to_csv(ARCHIVO_CSV, index=False)
        return df_i

def cargar_productos():
    df_base_prods = pd.DataFrame([
        {"Email_Emprendedora": CORREO_ADMIN, "Producto": "Kit de Velas Artesanales", "Precio": 250.0, "Categoria": "Decoración y Hogar", "Estado": "Querétaro", "Stock": 10, "Estado_Aprobacion": "Aprobado"},
        {"Email_Emprendedora": CORREO_ADMIN, "Producto": "Agenda Empoder-Arte 2026", "Precio": 380.0, "Categoria": "Papelería y Agendas", "Estado": "Querétaro", "Stock": 5, "Estado_Aprobacion": "Aprobado"}
    ])
    if os.path.exists(ARCHIVO_PRODUCTOS):
        try:
            df_p = pd.read_csv(ARCHIVO_PRODUCTOS)
            if df_p.empty:
                df_p = df_base_prods
                df_p.to_csv(ARCHIVO_PRODUCTOS, index=False)
            else:
                if "Estado_Aprobacion" not in df_p.columns:
                    df_p["Estado_Aprobacion"] = "Aprobado"
                if "Estado" not in df_p.columns:
                    df_p["Estado"] = "Querétaro"
                df_p.to_csv(ARCHIVO_PRODUCTOS, index=False)
            return df_p
        except Exception:
            df_base_prods.to_csv(ARCHIVO_PRODUCTOS, index=False)
            return df_base_prods
    else:
        df_base_prods.to_csv(ARCHIVO_PRODUCTOS, index=False)
        return df_base_prods

def cargar_oraciones():
    if os.path.exists(ARCHIVO_ORACIONES):
        try:
            return pd.read_csv(ARCHIVO_ORACIONES)
        except Exception:
            df = pd.DataFrame(columns=["Fecha", "Nombre", "Contacto", "Peticion"])
            df.to_csv(ARCHIVO_ORACIONES, index=False)
            return df
    else:
        df = pd.DataFrame(columns=["Fecha", "Nombre", "Contacto", "Peticion"])
        df.to_csv(ARCHIVO_ORACIONES, index=False)
        return df

def guardar_datos(df, archivo):
    df.to_csv(archivo, index=False)

# Control de Sesión
if "sesion_activa" not in st.session_state:
    st.session_state["sesion_activa"] = False
if "usuario_logueado" not in st.session_state:
    st.session_state["usuario_logueado"] = None
if "email_logueado" not in st.session_state:
    st.session_state["email_logueado"] = None
if "rol_usuario" not in st.session_state:
    st.session_state["rol_usuario"] = None
if "es_admin" not in st.session_state:
    st.session_state["es_admin"] = False
if "video_stream_activo" not in st.session_state:
    st.session_state["video_stream_activo"] = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
if "versiculo_dia" not in st.session_state:
    st.session_state["versiculo_dia"] = VERSICULOS_EMPRENDIMIENTO[0]

df_emprendedoras = cargar_datos()
img_logo = cargar_imagen_segura(LOGO_IMAGEN)

# ---------------------------------------------------------
# 2. ESTILOS VISUALES
# ---------------------------------------------------------
st.set_page_config(page_title="Empoder-Arte | Red Nacional", page_icon="👑", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700;800&family=Playfair+Display:ital,wght@0,600;0,700;1,400&display=swap');

    .brand-font {
        font-family: 'Cinzel', 'Playfair Display', Georgia, serif !important;
        letter-spacing: 1.5px;
    }

    .stApp {
        background: linear-gradient(180deg, #FFF0F5 0%, #FAFAFA 100%);
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
        width: 75px;
        height: 75px;
        border-radius: 50%;
        object-fit: cover;
        border: 3px solid #D81B60;
        margin-right: 15px;
        vertical-align: middle;
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
    </style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 3. HEADER
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

# ---------------------------------------------------------
# 4. PANTALLA INICIAL DE ACCESO Y REGISTROS
# ---------------------------------------------------------
if not st.session_state["sesion_activa"]:
    st.write("---")
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    
    with col_l2:
        st.markdown('<div class="card" style="text-align:center;"><h3 class="brand-font" style="color:#D81B60; margin-top:0;">👑 Bienvenida a Empoder-Arte</h3><p style="color:#555;">Selecciona tu modalidad de acceso a la plataforma:</p></div>', unsafe_allow_html=True)
        
        tab_login, tab_reg_cliente, tab_reg_emp_gratis, tab_reg_emp_vip = st.tabs([
            "🔑 Iniciar Sesión", 
            "👤 Registro Cliente", 
            "🌸 Registro Emprendedora Gratis", 
            "💳 Registro Emprendedora VIP ($25 MXN)"
        ])
        
        with tab_login:
            with st.form("form_login_landing"):
                email_in = st.text_input("Ingresa tu correo registrado:").strip().lower()
                btn_in = st.form_submit_button("Ingresar a la Plataforma ✨")
                
                if btn_in and email_in:
                    if email_in == CORREO_ADMIN:
                        st.session_state["sesion_activa"] = True
                        st.session_state["es_admin"] = True
                        st.session_state["rol_usuario"] = "Admin"
                        st.session_state["email_logueado"] = CORREO_ADMIN
                        st.session_state["usuario_logueado"] = "Larissa García (Fundadora)"
                        st.success("👑 Acceso Fundadora Aprobado.")
                        st.rerun()
                    else:
                        reg = df_emprendedoras[df_emprendedoras["Email"] == email_in]
                        if not reg.empty:
                            st.session_state["sesion_activa"] = True
                            st.session_state["email_logueado"] = email_in
                            st.session_state["usuario_logueado"] = reg.iloc[0]["Nombre"]
                            st.session_state["rol_usuario"] = reg.iloc[0]["Estado_Pago"]
                            st.success(f"¡Bienvenida {reg.iloc[0]['Nombre']}!")
                            st.rerun()
                        else:
                            st.error("Este correo no se encuentra registrado.")

        with tab_reg_cliente:
            with st.form("form_reg_cliente"):
                nom_c = st.text_input("Tu Nombre Completo")
                email_c = st.text_input("Correo Electrónico").strip().lower()
                cel_c = st.text_input("Número de Celular / WhatsApp")
                curp_c_val = st.text_input("Clave CURP (18 caracteres)").strip().upper()
                estado_c = st.selectbox("Estado donde te ubicas", ESTADOS_MEXICO)
                
                st.write("<b>🛡️ Carga de Foto e Identificación Antifraude:</b>", unsafe_allow_html=True)
                foto_c = st.file_uploader("Subir Foto de Perfil", type=["jpg", "png", "jpeg"], key="c_foto")
                ine_c = st.file_uploader("Subir Foto de INE (Frente y Vuelta)", type=["jpg", "png", "pdf"], key="c_ine")
                
                btn_reg_c = st.form_submit_button("✨ Registrarme como Cliente Gratis")
                
                if btn_reg_c and email_c and nom_c and cel_c and curp_c_val:
                    if not df_emprendedoras[df_emprendedoras["Email"] == email_c].empty:
                        st.error("Este correo ya está en uso.")
                    elif len(curp_c_val) != 18:
                        st.error("Ingresa una CURP válida de 18 caracteres.")
                    else:
                        foto_url_base64 = convertir_imagen_a_base64(foto_c)
                        lat, lon = COORDENADAS_ESTADOS.get(estado_c, (23.6345, -102.5528))
                        
                        nueva_row = pd.DataFrame([{
                            "Email": email_c, "Celular": cel_c, "Nombre": nom_c, "Negocio": "Cliente Visitante",
                            "Tipo_Oferta": "Cliente", "Categoria": "General", "Estado": estado_c,
                            "Ciudad": "Por definir", "Colonia": "Por definir", "Contacto": cel_c,
                            "Descripcion": "Cliente de la comunidad", "Historia": "Cliente activa.", "Estado_Pago": "Gratis",
                            "Metodo_Pago": "N/A", "Estado_Aprobacion": "Aprobado",
                            "Foto_Perfil": foto_url_base64,
                            "INE_Doc": "Adjuntado" if ine_c else "Pendiente",
                            "CURP_Valor": curp_c_val,
                            "lat": lat, "lon": lon
                        }])
                        df_emprendedoras = pd.concat([df_emprendedoras, nueva_row], ignore_index=True)
                        guardar_datos(df_emprendedoras, ARCHIVO_CSV)
                        
                        st.session_state["sesion_activa"] = True
                        st.session_state["email_logueado"] = email_c
                        st.session_state["usuario_logueado"] = nom_c
                        st.session_state["rol_usuario"] = "Cliente"
                        st.success("¡Registro completado!")
                        st.rerun()

        with tab_reg_emp_gratis:
            st.markdown("<b style='color:#D81B60;'>🌸 Registro Gratuito para Emprendedoras (Directorio y Marketplace)</b>", unsafe_allow_html=True)
            tipo_oferta_g = st.radio("¿Qué ofrece tu negocio?", ["Servicios", "Productos"], horizontal=True, key="reg_g_tipo")
            cat_opciones_g = LISTA_SERVICIOS if tipo_oferta_g == "Servicios" else LISTA_PRODUCTOS

            with st.form("form_reg_emp_gratis"):
                categoria_sel_g = st.selectbox("Categoría de tu oferta", cat_opciones_g)
                email_g = st.text_input("Correo Electrónico").strip().lower()
                cel_g = st.text_input("Número de Celular / WhatsApp")
                nombre_g = st.text_input("Tu Nombre Completo")
                negocio_g = st.text_input("Nombre de tu Emprendimiento")
                curp_g_val = st.text_input("Clave CURP Oficial (18 caracteres)").strip().upper()
                
                col_g1, col_g2 = st.columns(2)
                with col_g1:
                    estado_g = st.selectbox("Estado", ESTADOS_MEXICO, key="e_g_est")
                    ciudad_g = st.text_input("Ciudad / Municipio", key="e_g_ciud")
                with col_g2:
                    colonia_g = st.text_input("Colonia", key="e_g_col")
                    contacto_g = st.text_input("Contacto Público (Teléfono/Correo)", key="e_g_cont")
                    
                desc_g = st.text_area("Descripción de lo que ofreces")
                historia_g = st.text_area("Cuéntanos tu Historia Emprendedora")
                
                st.write("<b>🛡️ Carga Obligatoria de Identificación y Foto:</b>", unsafe_allow_html=True)
                foto_g = st.file_uploader("Subir Foto de Perfil / Logo", type=["jpg", "png", "jpeg"], key="g_foto")
                ine_g = st.file_uploader("Subir Foto de INE Oficial (Frente/Vuelta)", type=["jpg", "png", "pdf"], key="g_ine")
                
                btn_reg_g = st.form_submit_button("🌸 Enviar Registro Gratis para Revisión")
                
                if btn_reg_g and email_g and nombre_g and negocio_g and cel_g and curp_g_val:
                    if not df_emprendedoras[df_emprendedoras["Email"] == email_g].empty:
                        st.error("Este correo ya está registrado.")
                    elif len(curp_g_val) != 18:
                        st.error("La CURP debe contener exactamente 18 caracteres.")
                    else:
                        foto_url_base64 = convertir_imagen_a_base64(foto_g)
                        estado_registro = "Aprobado" if email_g == CORREO_ADMIN else "Pendiente"
                        lat, lon = COORDENADAS_ESTADOS.get(estado_g, (23.6345, -102.5528))
                        
                        nueva_row = pd.DataFrame([{
                            "Email": email_g, "Celular": cel_g, "Nombre": nombre_g, "Negocio": negocio_g,
                            "Tipo_Oferta": tipo_oferta_g, "Categoria": categoria_sel_g, "Estado": estado_g,
                            "Ciudad": ciudad_g, "Colonia": colonia_g, "Contacto": contacto_g,
                            "Descripcion": desc_g, "Historia": historia_g, "Estado_Pago": "Emprendedora Gratis", "Metodo_Pago": "Gratis",
                            "Estado_Aprobacion": estado_registro,
                            "Foto_Perfil": foto_url_base64,
                            "INE_Doc": "Adjuntado" if ine_g else "Pendiente",
                            "CURP_Valor": curp_g_val,
                            "lat": lat, "lon": lon
                        }])
                        df_emprendedoras = pd.concat([df_emprendedoras, nueva_row], ignore_index=True)
                        guardar_datos(df_emprendedoras, ARCHIVO_CSV)
                        
                        st.session_state["sesion_activa"] = True
                        st.session_state["email_logueado"] = email_g
                        st.session_state["usuario_logueado"] = nombre_g
                        st.session_state["rol_usuario"] = "Emprendedora Gratis"
                        st.success("¡Registro enviado! Quedó en revisión para aprobación exclusiva de la Fundadora (Larissa García).")
                        st.rerun()

        with tab_reg_emp_vip:
            st.markdown("<b style='color:#D81B60;'>💳 Registro Emprendedora VIP ($25 MXN/mes) — Acceso Completo</b>", unsafe_allow_html=True)
            tipo_oferta_v = st.radio("¿Qué ofrece tu negocio?", ["Servicios", "Productos"], horizontal=True, key="reg_v_tipo")
            cat_opciones_v = LISTA_SERVICIOS if tipo_oferta_v == "Servicios" else LISTA_PRODUCTOS

            with st.form("form_reg_emp_vip"):
                categoria_sel_v = st.selectbox("Categoría específica", cat_opciones_v)
                email_v = st.text_input("Correo Electrónico").strip().lower()
                cel_v = st.text_input("Número de Celular / WhatsApp")
                nombre_v = st.text_input("Tu Nombre Completo")
                negocio_v = st.text_input("Nombre de tu Emprendimiento")
                curp_v_val = st.text_input("Clave CURP Oficial (18 caracteres)").strip().upper()
                
                col_v1, col_v2 = st.columns(2)
                with col_v1:
                    estado_v = st.selectbox("Estado", ESTADOS_MEXICO, key="e_v_est")
                    ciudad_v = st.text_input("Ciudad / Municipio", key="e_v_ciud")
                with col_v2:
                    colonia_v = st.text_input("Colonia", key="e_v_col")
                    contacto_v = st.text_input("Contacto Público (Teléfono/Correo)", key="e_v_cont")
                    
                desc_v = st.text_area("Descripción de tu negocio")
                historia_v = st.text_area("Cuéntanos tu Historia Emprendedora")
                
                st.write("<b>🛡️ Carga Obligatoria de Identificación y Foto:</b>", unsafe_allow_html=True)
                foto_v = st.file_uploader("Subir Foto de Perfil / Logo", type=["jpg", "png", "jpeg"], key="v_foto")
                ine_v = st.file_uploader("Subir Identificación INE Oficial (Frente/Vuelta)", type=["jpg", "png", "pdf"], key="v_ine")
                
                metodo_v = st.selectbox("Método de Pago", ["Mercado Pago / Tarjeta", "Transferencia SPEI"])
                btn_reg_v = st.form_submit_button("💳 Registrar Emprendimiento VIP y Enviar a Revisión")
                
                if btn_reg_v and email_v and nombre_v and negocio_v and cel_v and curp_v_val:
                    if not df_emprendedoras[df_emprendedoras["Email"] == email_v].empty:
                        st.error("Este correo ya está registrado.")
                    elif len(curp_v_val) != 18:
                        st.error("La CURP debe contener exactamente 18 caracteres.")
                    else:
                        foto_url_base64 = convertir_imagen_a_base64(foto_v)
                        estado_registro = "Aprobado" if email_v == CORREO_ADMIN else "Pendiente"
                        lat, lon = COORDENADAS_ESTADOS.get(estado_v, (23.6345, -102.5528))
                        
                        nueva_row = pd.DataFrame([{
                            "Email": email_v, "Celular": cel_v, "Nombre": nombre_v, "Negocio": negocio_v,
                            "Tipo_Oferta": tipo_oferta_v, "Categoria": categoria_sel_v, "Estado": estado_v,
                            "Ciudad": ciudad_v, "Colonia": colonia_v, "Contacto": contacto_v,
                            "Descripcion": desc_v, "Historia": historia_v, "Estado_Pago": "VIP", "Metodo_Pago": metodo_v,
                            "Estado_Aprobacion": estado_registro,
                            "Foto_Perfil": foto_url_base64,
                            "INE_Doc": "Adjuntado" if ine_v else "Pendiente",
                            "CURP_Valor": curp_v_val,
                            "lat": lat, "lon": lon
                        }])
                        df_emprendedoras = pd.concat([df_emprendedoras, nueva_row], ignore_index=True)
                        guardar_datos(df_emprendedoras, ARCHIVO_CSV)
                        
                        st.session_state["sesion_activa"] = True
                        st.session_state["email_logueado"] = email_v
                        st.session_state["usuario_logueado"] = nombre_v
                        st.session_state["rol_usuario"] = "VIP"
                        st.success("¡Registro VIP enviado! En espera de validación exclusiva por Larissa García.")
                        st.rerun()

# ---------------------------------------------------------
# 5. APLICACIÓN PRINCIPAL TRAS INICIAR SESIÓN
# ---------------------------------------------------------
else:
    with st.sidebar:
        if img_logo:
            st.image(img_logo, use_container_width=True)
        else:
            st.markdown('<h2 class="brand-font" style="text-align:center; color:white;">👑 Empoder-Arte</h2>', unsafe_allow_html=True)
            
        st.write("---")
        st.success(f"👤 Sesión Activa:\n**{st.session_state['usuario_logueado']}**\n\nRol: {st.session_state['rol_usuario']}")
        
        if st.button("🚪 Cerrar Sesión"):
            st.session_state["sesion_activa"] = False
            st.session_state["es_admin"] = False
            st.session_state["email_logueado"] = None
            st.session_state["usuario_logueado"] = None
            st.session_state["rol_usuario"] = None
            st.rerun()

    titulos_pestañas = [
        "🌸 Directorio de Servicios",
        "🛍️ Marketplace",
        "🗺️ Mapa México",
        "🔴 En Vivo",
        "🙏 Petición Oración",
        "💼 Mi Oficina",
        "📚 Educación",
    ]

    if st.session_state["es_admin"]:
        titulos_pestañas.append("📊 Dashboard Admin")

    titulos_pestañas.append("💳 Anunciar mi Negocio ($25 MXN)")

    pestañas = st.tabs(titulos_pestañas)

    # --- PESTAÑA 1: DIRECTORIO E HISTORIA EMPRENDEDORA ---
    with pestañas[0]:
        st.markdown('<h3 class="brand-font" style="color:#D81B60;">🌸 Directorio de Servicios e Historias de Vida</h3>', unsafe_allow_html=True)
        
        df_servicios = df_emprendedoras[
            (df_emprendedoras["Tipo_Oferta"] == "Servicios") & 
            (df_emprendedoras["Estado_Aprobacion"] == "Aprobado")
        ].copy()
        
        if df_servicios.empty:
            st.info("Aún no hay emprendedoras aprobadas en el directorio.")
        else:
            for idx, row in df_servicios.reset_index().iterrows():
                es_propietaria = (row.get('Email') == st.session_state["email_logueado"]) or st.session_state["es_admin"]
                es_fundadora = (row.get('Email') == CORREO_ADMIN)
                nombre_mostrar = NOMBRE_FUNDADORA if es_fundadora else row['Nombre']
                contacto_valor = CORREO_ADMIN if es_fundadora else row.get('Contacto', CORREO_ADMIN)
                foto_url = row.get('Foto_Perfil', 'https://via.placeholder.com/150')
                
                st.markdown(f"""
                    <div class="card">
                        <div style="display: flex; align-items: center; margin-bottom: 12px;">
                            <img src="{foto_url}" class="profile-img-header" alt="Foto de Perfil">
                            <div>
                                <h4 class="brand-font" style="color: #D81B60; margin:0;">💼 {row['Negocio']}</h4>
                                <p style="color: #333; margin:0; font-size:14px;"><b>Por:</b> {nombre_mostrar} | 📧 {row.get('Email','N/A')} | 📱 {row.get('Celular','N/A')}</p>
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

                if es_propietaria:
                    with st.expander(f"✏️ Editar Mi Perfil, Foto e Historia ({row['Negocio']})"):
                        with st.form(f"form_edit_{idx}"):
                            nuevo_nom_neg = st.text_input("Nombre del Negocio", value=row['Negocio'])
                            nuevo_email_e = st.text_input("Correo Electrónico", value=row.get('Email', ''))
                            nuevo_cel_e = st.text_input("Celular / WhatsApp", value=str(row.get('Celular', '')))
                            nueva_curp_e = st.text_input("CURP", value=str(row.get('CURP_Valor', '')))
                            nueva_historia = st.text_area("Mi Historia Emprendedora", value=row.get('Historia', ''))
                            nuevo_est = st.selectbox("Estado", ESTADOS_MEXICO, index=ESTADOS_MEXICO.index(row['Estado']) if row['Estado'] in ESTADOS_MEXICO else 0)
                            nueva_ciud = st.text_input("Ciudad / Municipio", value=row.get('Ciudad', ''))
                            nueva_col = st.text_input("Colonia", value=row.get('Colonia', ''))
                            nuevo_cont = st.text_input("Contacto Público", value=contacto_valor)
                            nueva_desc = st.text_area("Descripción de Oferta", value=row['Descripcion'])
                            
                            nueva_foto_edit = st.file_uploader("Actualizar Foto de Perfil", type=["jpg", "png", "jpeg"], key=f"edit_foto_{idx}")
                            
                            btn_guardar_edit = st.form_submit_button("💾 Guardar Cambios de Perfil")
                            
                            if btn_guardar_edit:
                                lat_e, lon_e = COORDENADAS_ESTADOS.get(nuevo_est, (23.6345, -102.5528))
                                idx_real = row['index'] if 'index' in row else idx
                                df_emprendedoras.loc[idx_real, 'Negocio'] = nuevo_nom_neg
                                df_emprendedoras.loc[idx_real, 'Email'] = nuevo_email_e
                                df_emprendedoras.loc[idx_real, 'Celular'] = nuevo_cel_e
                                df_emprendedoras.loc[idx_real, 'CURP_Valor'] = nueva_curp_e
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
                                st.success("¡Perfil e historia actualizados con éxito!")
                                st.rerun()

    # --- PESTAÑA 2: MARKETPLACE DE PRODUCTOS (AGREGAR, EDITAR Y ELIMINAR) ---
    with pestañas[1]:
        st.markdown('<h3 class="brand-font" style="color:#D81B60;">🛍️ Marketplace Nacional Empoder-Arte</h3>', unsafe_allow_html=True)
        df_prods_todos = cargar_productos()
        
        # BOTÓN PARA PUBLICAR NUEVO PRODUCTO EN MARKETPLACE
        if st.session_state["rol_usuario"] in ["VIP", "Emprendedora Gratis", "Admin", "Administradora"]:
            with st.expander("➕ AGREGAR NUEVA PUBLICACIÓN AL MARKETPLACE"):
                with st.form("form_nuevo_prod_market"):
                    prod_nombre = st.text_input("Nombre del Producto")
                    prod_precio = st.number_input("Precio ($ MXN)", min_value=1.0, value=100.0, step=10.0)
                    prod_cat = st.selectbox("Categoría", LISTA_PRODUCTOS)
                    prod_estado = st.selectbox("Estado de Envío / Ubicación", ESTADOS_MEXICO)
                    prod_stock = st.number_input("Unidades en Stock", min_value=1, value=5, step=1)
                    btn_crear_prod = st.form_submit_button("🚀 Enviar Publicación a Revisión")
                    
                    if btn_crear_prod and prod_nombre:
                        estado_ap = "Aprobado" if st.session_state["es_admin"] else "Pendiente"
                        nuevo_p_df = pd.DataFrame([{
                            "Email_Emprendedora": st.session_state["email_logueado"],
                            "Producto": prod_nombre,
                            "Precio": float(prod_precio),
                            "Categoria": prod_cat,
                            "Estado": prod_estado,
                            "Stock": int(prod_stock),
                            "Estado_Aprobacion": estado_ap
                        }])
                        df_prods_todos = pd.concat([df_prods_todos, nuevo_p_df], ignore_index=True)
                        guardar_datos(df_prods_todos, ARCHIVO_PRODUCTOS)
                        if estado_ap == "Aprobado":
                            st.success("¡Producto publicado en el Marketplace!")
                        else:
                            st.info("¡Producto registrado! Quedó en revisión para aprobación exclusiva de la Fundadora.")
                        st.rerun()
                        
        st.write("---")
        df_prods = df_prods_todos[df_prods_todos["Estado_Aprobacion"] == "Aprobado"].copy()

        if df_prods.empty:
            st.info("No hay productos aprobados disponibles por el momento.")
        else:
            cols = st.columns(3)
            for idx, row in df_prods.reset_index().iterrows():
                es_autora_o_fundadora = (st.session_state["email_logueado"] == row["Email_Emprendedora"]) or (st.session_state["email_logueado"] == CORREO_ADMIN) or st.session_state["es_admin"]
                
                with cols[idx % 3]:
                    st.markdown(f"""
                        <div class="card" style="text-align:center;">
                            <h4 class="brand-font" style="color:#D81B60; margin:0;">🛍️ {row['Producto']}</h4>
                            <p style="color:#D81B60; font-weight:bold; font-size:20px;">${row['Precio']:,.2f} MXN</p>
                            <p style="font-size:12px; color:#555;">📍 {row.get('Estado', 'México')} | Vendedora: {row['Email_Emprendedora']}<br>Stock: <b>{row['Stock']}</b></p>
                            <span style="background-color:#F8BBD0; color:#D81B60; padding:3px 8px; border-radius:10px; font-size:11px; font-weight:bold;">{row['Categoria']}</span>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    if es_autora_o_fundadora:
                        col_btn1, col_btn2 = st.columns(2)
                        with col_btn1:
                            with st.popover("✏️ Editar"):
                                with st.form(f"form_edit_prod_{idx}"):
                                    edit_p_nom = st.text_input("Producto", value=row["Producto"])
                                    edit_p_precio = st.number_input("Precio", value=float(row["Precio"]))
                                    edit_p_cat = st.selectbox("Categoría", LISTA_PRODUCTOS, index=LISTA_PRODUCTOS.index(row["Categoria"]) if row["Categoria"] in LISTA_PRODUCTOS else 0)
                                    edit_p_stock = st.number_input("Stock", value=int(row["Stock"]))
                                    btn_salvar_prod = st.form_submit_button("💾 Guardar")
                                    
                                    if btn_salvar_prod:
                                        idx_m = row['index'] if 'index' in row else idx
                                        df_prods_todos.loc[idx_m, "Producto"] = edit_p_nom
                                        df_prods_todos.loc[idx_m, "Precio"] = float(edit_p_precio)
                                        df_prods_todos.loc[idx_m, "Categoria"] = edit_p_cat
                                        df_prods_todos.loc[idx_m, "Stock"] = int(edit_p_stock)
                                        guardar_datos(df_prods_todos, ARCHIVO_PRODUCTOS)
                                        st.success("¡Producto actualizado!")
                                        st.rerun()

                        with col_btn2:
                            if st.button("🗑️ Borrar", key=f"btn_del_prod_{idx}"):
                                idx_eliminar = row['index'] if 'index' in row else idx
                                df_prods_todos = df_prods_todos.drop(index=idx_eliminar).reset_index(drop=True)
                                guardar_datos(df_prods_todos, ARCHIVO_PRODUCTOS)
                                st.success(f"¡Publicación eliminada!")
                                st.rerun()

    # --- PESTAÑA 3: MAPA INTERACTIVO DE MÉXICO ---
    with pestañas[2]:
        st.markdown('<h3 class="brand-font" style="color:#D81B60;">🗺️ Mapa Nacional de Emprendedoras Empoder-Arte</h3>', unsafe_allow_html=True)
        df_mapa = df_emprendedoras[df_emprendedoras["Estado_Aprobacion"] == "Aprobado"].copy()
        if not df_mapa.empty:
            df_mapa["lat"] = df_mapa["Estado"].map(lambda x: COORDENADAS_ESTADOS.get(x, (23.6345, -102.5528))[0] + np.random.uniform(-0.05, 0.05))
            df_mapa["lon"] = df_mapa["Estado"].map(lambda x: COORDENADAS_ESTADOS.get(x, (23.6345, -102.5528))[1] + np.random.uniform(-0.05, 0.05))
            st.map(df_mapa[["lat", "lon"]], zoom=4)

    # --- PESTAÑA 4: TRANSMISIONES EN VIVO (EXCLUSIVO VIP Y ADMIN) ---
    with pestañas[3]:
        st.markdown('<h3 class="brand-font" style="color:#D81B60;">🔴 Sala de Live Stream Empoder-Arte</h3>', unsafe_allow_html=True)
        if st.session_state["rol_usuario"] in ["VIP", "Admin", "Administradora"]:
            st.video(st.session_state["video_stream_activo"])
        else:
            st.warning("🔒 El acceso a las transmisiones en vivo es exclusivo para Emprendedoras VIP ($25.00 MXN/mes).")

    # --- PESTAÑA 5: PETICIÓN PRIVADA DE ORACIÓN ---
    with pestañas[4]:
        st.markdown('<h3 class="brand-font" style="color:#D81B60;">🙏 Petición Privada de Oración</h3>', unsafe_allow_html=True)
        with st.form("form_oracion_privada", clear_on_submit=True):
            texto_peticion = st.text_area("Escribe aquí tu petición o motivo de oración:")
            btn_oracion = st.form_submit_button("🔒 Enviar Petición Confidencial")
            if btn_oracion and texto_peticion:
                df_oraciones = cargar_oraciones()
                nueva_oracion = pd.DataFrame([{
                    "Fecha": str(date.today()),
                    "Nombre": st.session_state["usuario_logueado"],
                    "Contacto": st.session_state["email_logueado"],
                    "Peticion": texto_peticion
                }])
                df_oraciones = pd.concat([df_oraciones, nueva_oracion], ignore_index=True)
                guardar_datos(df_oraciones, ARCHIVO_ORACIONES)
                st.success("🙏 Tu petición ha sido enviada confidencialmente a Larissa García.")

    # --- PESTAÑA 6: MI OFICINA (EXCLUSIVO VIP Y ADMIN) ---
    with pestañas[5]:
        st.markdown('<h3 class="brand-font" style="color:#D81B60;">💼 Mi Oficina | Empoder-Arte</h3>', unsafe_allow_html=True)
        if st.session_state["rol_usuario"] in ["VIP", "Admin", "Administradora"]:
            st.write(f"Bienvenida a tu panel de administración financiera y ventas, **{st.session_state['usuario_logueado']}**.")
        else:
            st.warning("🔒 Las herramientas de control financiero, clientes e inventario son exclusivas para la Suscripción VIP ($25 MXN/mes).")

    # --- PESTAÑA 7: EDUCACIÓN EXCLUSIVA (EXCLUSIVO VIP Y ADMIN) ---
    with pestañas[6]:
        st.markdown('<h3 class="brand-font" style="color:#D81B60;">📚 Capacitación y Talleres Empoder-Arte</h3>', unsafe_allow_html=True)
        if st.session_state["rol_usuario"] in ["VIP", "Admin", "Administradora"]:
            st.video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        else:
            st.warning("🔒 Los talleres educativos de costos y marketing son exclusivos para Emprendedoras VIP.")

    # --- DASHBOARD ADMIN EXCLUSIVO DE LARISSA GARCÍA (FUNDADORA) ---
    idx_pago = 7
    if st.session_state["es_admin"]:
        idx_pago = 8
        with pestañas[7]:
            st.markdown('<h3 class="brand-font" style="color:#D81B60;">👑 Módulo Exclusivo de Aprobación de Larissa García (Fundadora)</h3>', unsafe_allow_html=True)
            
            tab_aprob_emp, tab_aprob_prod, tab_bd_general = st.tabs([
                "✅ Aprobación de Emprendedoras", 
                "🛍️ Aprobación de Productos Marketplace", 
                "📊 Base de Datos General"
            ])
            
            with tab_aprob_emp:
                st.subheader("Solicitudes de Emprendedoras Pendientes de Aprobación")
                df_pendientes = df_emprendedoras[df_emprendedoras["Estado_Aprobacion"] == "Pendiente"]
                
                if df_pendientes.empty:
                    st.info("No hay perfiles pendientes de aprobación.")
                else:
                    for idx_p, row_p in df_pendientes.reset_index().iterrows():
                        st.markdown(f"""
                            <div class="card">
                                <b>Emprendedora:</b> {row_p['Nombre']} ({row_p['Email']})<br>
                                <b>Negocio:</b> {row_p['Negocio']} ({row_p['Tipo_Oferta']} - {row_p['Categoria']})<br>
                                <b>Ubicación:</b> {row_p['Estado']} • {row_p['Ciudad']}<br>
                                <b>CURP:</b> <code>{row_p.get('CURP_Valor','N/A')}</code> | <b>INE:</b> {row_p.get('INE_Doc','N/A')}
                            </div>
                        """, unsafe_allow_html=True)
                        if st.button(f"✅ Autorizar Perfil de {row_p['Nombre']}", key=f"btn_admin_aprob_{idx_p}"):
                            idx_orig = row_p['index'] if 'index' in row_p else idx_p
                            df_emprendedoras.loc[idx_orig, "Estado_Aprobacion"] = "Aprobado"
                            guardar_datos(df_emprendedoras, ARCHIVO_CSV)
                            st.success(f"¡Perfil de {row_p['Nombre']} aprobado por la Fundadora!")
                            st.rerun()

            with tab_aprob_prod:
                st.subheader("Productos Pendientes para el Marketplace")
                df_prods_todos = cargar_productos()
                df_prods_pend = df_prods_todos[df_prods_todos["Estado_Aprobacion"] == "Pendiente"]
                
                if df_prods_pend.empty:
                    st.info("No hay productos pendientes de revisión.")
                else:
                    for idx_pr, row_pr in df_prods_pend.reset_index().iterrows():
                        st.markdown(f"""
                            <div class="card">
                                <b>Producto:</b> {row_pr['Producto']} | <b>Precio:</b> ${row_pr['Precio']} MXN<br>
                                <b>Vendedora:</b> {row_pr['Email_Emprendedora']}<br>
                                <b>Categoría:</b> {row_pr['Categoria']} | <b>Stock:</b> {row_pr['Stock']}
                            </div>
                        """, unsafe_allow_html=True)
                        
                        col_ap, col_el = st.columns(2)
                        with col_ap:
                            if st.button(f"✅ Autorizar '{row_pr['Producto']}'", key=f"btn_aprob_prod_{idx_pr}"):
                                idx_p_orig = row_pr['index'] if 'index' in row_pr else idx_pr
                                df_prods_todos.loc[idx_p_orig, "Estado_Aprobacion"] = "Aprobado"
                                guardar_datos(df_prods_todos, ARCHIVO_PRODUCTOS)
                                st.success(f"¡Producto '{row_pr['Producto']}' publicado en el Marketplace!")
                                st.rerun()
                        with col_el:
                            if st.button(f"🗑️ Rechazar / Borrar '{row_pr['Producto']}'", key=f"btn_del_pend_{idx_pr}"):
                                idx_p_orig = row_pr['index'] if 'index' in row_pr else idx_pr
                                df_prods_todos = df_prods_todos.drop(index=idx_p_orig).reset_index(drop=True)
                                guardar_datos(df_prods_todos, ARCHIVO_PRODUCTOS)
                                st.success(f"¡Producto '{row_pr['Producto']}' rechazado!")
                                st.rerun()

            with tab_bd_general:
                st.subheader("Registros Globales")
                st.dataframe(df_emprendedoras)

    # --- PESTAÑA FINAL: PAGO Y REGISTRO ---
    with pestañas[idx_pago]:
        st.markdown('<h3 class="brand-font" style="color:#D81B60;">💳 Anunciar mi Negocio / Registro de Suscripción VIP ($25.00 MXN / mes)</h3>', unsafe_allow_html=True)