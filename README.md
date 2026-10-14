# JJTrading_ · Plan de operación

App web para generar el informe de plan de operación (solo largos) de cualquier acción:
zona de entrada, stop, objetivos, mapa de niveles, tendencia, confirmación 1H y avisos.
Datos de Yahoo Finance. Mismo método que el cuaderno de Colab.

## Archivos

| Archivo | Para qué sirve |
|---|---|
| `app.py` | La pantalla: casilla de ticker, selector de bolsa y botón |
| `niveles.py` | El cálculo de niveles y el informe (reglas calibradas; no cambiar parámetros sin recalibrar) |
| `requirements.txt` | Librerías que instala Streamlit Cloud |
| `.streamlit/config.toml` | Colores de la app |

## Publicarla (una sola vez)

1. Entra en [share.streamlit.io](https://share.streamlit.io) y pulsa **Continue with GitHub** con tu cuenta `jjesusmj`.
2. Pulsa **Create app** → **Deploy a public app from GitHub**.
3. Rellena:
   - **Repository:** `jjesusmj/jjtrading-informes`
   - **Branch:** `main`
   - **Main file path:** `app.py`
   - **App URL:** el nombre que quieras, por ejemplo `jjtrading-informes`
4. Pulsa **Deploy**. La primera vez tarda 2-3 minutos en instalar las librerías.

## Contraseña (recomendado)

En la app publicada: **⋮ → Settings → Secrets** y escribe:

```toml
APP_PASSWORD = "la-contraseña-que-quieras"
```

Guarda. A partir de ahí la app pide la contraseña antes de mostrar nada.

## En el móvil

Abre la dirección de la app en Safari → botón **Compartir** → **Añadir a pantalla de inicio**.
Queda como un icono más del iPhone.

## Actualizar

Cualquier cambio que se suba a GitHub en la rama `main` se publica solo en 1-2 minutos.

## Si falla

- *"Yahoo no devuelve datos suficientes"*: revisa el ticker y la bolsa.
- *"No se pudo generar el informe"*: Yahoo a veces limita peticiones desde servidores en la nube. Prueba en unos minutos.
- La app se "duerme" si nadie la usa en unos días; al abrirla tarda unos segundos en despertar.

Informe automático con fines de análisis personal. No es una recomendación de inversión.
