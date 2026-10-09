# 👑 Empoder-Arte

**Plataforma web de la Red Nacional de Emprendedoras, Ventas y Capacitación.**

Empoder-Arte es una aplicación construida con [Streamlit](https://streamlit.io/) que impulsa el
crecimiento, los servicios y la comunidad de la marca: registro de emprendedoras, marketplace de
productos y servicios, finanzas, agenda, peticiones de oración, lives y evaluaciones.

> Fundadora: **Larissa García**

---

## ✨ Características principales

- **Inicio** — Bienvenida, propuesta de valor y visión de la marca.
- **Programas / Servicios** — Catálogo modular de talleres, consultorías y servicios.
- **Comunidad / Registro** — Formulario interactivo para captar datos de usuarias y clientas.
- **Contacto & Redes** — Información de contacto directa y canales de la comunidad.
- **Seguridad** — Cifrado de datos sensibles mediante AES-128 (Fernet) y gestión de sesiones.

---

## 🧰 Requisitos previos

- [Python 3.9+](https://www.python.org/downloads/)
- `pip` (gestor de paquetes de Python)

---

## 🚀 Instalación y ejecución local

1. **Clona o descarga** el proyecto y entra en la carpeta raíz:

   ```bash
   cd app_empoder_arte
   ```

2. **Crea y activa un entorno virtual** (recomendado):

   ```bash
   # Windows (PowerShell)
   python -m venv .venv
   .venv\Scripts\Activate.ps1

   # macOS / Linux
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Instala las dependencias:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Ejecuta la aplicación:**

   ```bash
   streamlit run app.py
   ```

   Streamlit abrirá automáticamente la app en tu navegador (por defecto en
   `http://localhost:8501`).

---

## ☁️ Despliegue en Streamlit Cloud (base de datos Supabase)

La plataforma usa una base de datos **PostgreSQL en Supabase** como fuente de verdad. Tanto la
conexión (`DB_URL`) como la contraseña del panel admin (`ADMIN_PASS`) se resuelven a través de
secrets y **nunca** deben quedar escritas en el código ni en el repositorio.

1. En Streamlit Cloud, abre tu app y ve a **Settings → Secrets**.
2. Agrega la clave `DB_URL` con la cadena de conexión del *pooler* de Supabase. Usa este formato
   (reemplaza `TU_PASSWORD` por tu contraseña real, con los caracteres especiales
   *percent-encoded*):

   ```toml
   DB_URL = "postgresql://postgres.sqlfcnoyijqvocabialv:TU_PASSWORD@aws-1-us-west-2.pooler.supabase.com:6543/postgres"
   ```

   En el mismo apartado **Settings → Secrets**, agrega también la clave `ADMIN_PASS` con la
   contraseña de la administradora/fundadora (el login del panel admin). Si no la defines, la app
   usa un valor por defecto de compatibilidad, pero por seguridad **debe** configurarse como secret
   (el repositorio es público):

   ```toml
   ADMIN_PASS = "TU_PASSWORD_ADMIN"
   ```

   Parámetros del pooler compartido de Supabase:

   - **host:** `aws-1-us-west-2.pooler.supabase.com`
   - **port:** `6543`
   - **database:** `postgres`
   - **user:** `postgres.sqlfcnoyijqvocabialv`

   > Si tu contraseña contiene caracteres especiales (`*`, `@`, `:`, etc.), debes
   > *percent-encode*-arlos en la cadena de conexión (por ejemplo, `*` se escribe `%2A`).

3. Localmente, las mismas claves `DB_URL` y `ADMIN_PASS` viven en `.streamlit/secrets.toml`
   (archivo *gitignored*, **no se versiona**).

### 🔄 Migración de datos (una sola vez)

El script `migrar_a_supabase.py` traslada los datos locales (SQLite + CSV) a Supabase sin pérdida.
Se ejecuta **una única vez en tu máquina local** (donde existen `empoder_arte.db` y
`.streamlit/secrets.toml`); **no** forma parte del despliegue en la nube ni de ningún CI.

### 📦 Dependencias nuevas

Para la conexión a PostgreSQL, `requirements.txt` incluye `psycopg2-binary` y `SQLAlchemy`.

---

## 📁 Estructura del proyecto

```
app_empoder_arte/
├── app.py              # Aplicación principal de Streamlit
├── requirements.txt    # Dependencias del proyecto
├── .gitignore          # Archivos y carpetas ignorados por Git
├── README.md           # Este archivo
└── *.csv / *.json      # Bases de datos locales de la plataforma
```

---

## 🔒 Datos y privacidad

Los archivos `secret.key`, `session.json` y `usuarios.json` contienen información sensible y
**no deben subirse al repositorio** (ya están incluidos en `.gitignore`). Los datos personales
sensibles se almacenan cifrados mediante algoritmos criptográficos AES-128 (Fernet).

---

## 📬 Contacto

Para más información sobre la comunidad Empoder-Arte, visita la sección **Contacto & Redes**
dentro de la aplicación.
