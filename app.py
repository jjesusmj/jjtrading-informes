import streamlit as st

st.set_page_config(page_title="JJTrading_ · Plan de operación", page_icon="📈", layout="wide")

# Contraseña opcional: si en Streamlit Cloud defines APP_PASSWORD en "Secrets", la app la pide
try:
    clave = st.secrets.get("APP_PASSWORD", "")
except Exception:          # sin fichero de secretos: app sin contraseña
    clave = ""
if clave and not st.session_state.get("ok"):
    st.markdown("### JJTrading_")
    if st.text_input("Contraseña", type="password") == clave:
        st.session_state["ok"] = True
        st.rerun()
    st.stop()

st.navigation([
    st.Page("paginas/informe.py", title="Informe", icon="📈", default=True),
    st.Page("paginas/seguimiento.py", title="Seguimiento", icon="⭐"),
    st.Page("paginas/resultados.py", title="Resultados", icon="🎯"),
    st.Page("paginas/riesgo.py", title="Análisis acción", icon="🔍"),
]).run()
