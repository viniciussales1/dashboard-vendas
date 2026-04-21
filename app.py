import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Teste do Sistema",
    page_icon="📊",
    layout="wide"
)

st.title("Sistema de Vendas")
st.write("Aplicação carregada com sucesso.")

arquivo = st.file_uploader("Envie um CSV", type=["csv"])

if arquivo is not None:
    try:
        df = pd.read_csv(arquivo)
        st.success("Arquivo carregado com sucesso.")
        st.dataframe(df.head(20), use_container_width=True)
    except Exception as e:
        st.error(f"Erro ao ler o arquivo: {e}")
