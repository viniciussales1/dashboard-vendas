import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

st.set_page_config(page_title="Dashboard Seguro de Vendas", layout="wide")

# -----------------------------
# CONFIGURAÇÃO DE USUÁRIO
# -----------------------------
USUARIO_CORRETO = "admin"
SENHA_CORRETA = "1234"

# -----------------------------
# CONTROLE DE SESSÃO
# -----------------------------
if "logado" not in st.session_state:
    st.session_state.logado = False

# -----------------------------
# FUNÇÃO DE LOGIN
# -----------------------------
def tela_login():
    st.title("Área Segura do Sistema")
    st.subheader("Faça login para acessar o dashboard")

    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")

    if st.button("Entrar"):
        if usuario == USUARIO_CORRETO and senha == SENHA_CORRETA:
            st.session_state.logado = True
            st.success("Login realizado com sucesso.")
            st.rerun()
        else:
            st.error("Usuário ou senha inválidos.")

# -----------------------------
# FUNÇÃO DE LOGOUT
# -----------------------------
def botao_logout():
    if st.sidebar.button("Sair"):
        st.session_state.logado = False
        st.rerun()

# -----------------------------
# VALIDAÇÃO DO CSV
# -----------------------------
def validar_csv(df):
    colunas_necessarias = ["data", "produto", "quantidade", "preco", "estoque_atual"]
    faltando = [col for col in colunas_necessarias if col not in df.columns]

    if faltando:
        st.error(f"O arquivo não contém as colunas obrigatórias: {faltando}")
        return None

    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df["quantidade"] = pd.to_numeric(df["quantidade"], errors="coerce")
    df["preco"] = pd.to_numeric(df["preco"], errors="coerce")
    df["estoque_atual"] = pd.to_numeric(df["estoque_atual"], errors="coerce")

    df = df.dropna(subset=["data", "produto", "quantidade", "preco", "estoque_atual"])

    if df.empty:
        st.error("O arquivo ficou vazio após a limpeza dos dados.")
        return None

    return df

# -----------------------------
# DASHBOARD PRINCIPAL
# -----------------------------
def dashboard():
    st.title("Dashboard de Vendas e Estoque")
    st.write("Área protegida com upload seguro de arquivo CSV.")

    botao_logout()

    st.markdown("### Envie o arquivo CSV")
    arquivo = st.file_uploader("Selecione um arquivo CSV", type=["csv"])

    st.markdown("#### Formato esperado do arquivo")
    st.code(
        "data,produto,quantidade,preco,estoque_atual\n"
        "2025-01-01,Arroz,10,5.50,30\n"
        "2025-01-01,Feijao,8,7.00,20"
    )

    if arquivo is not None:
        try:
            df = pd.read_csv(arquivo)
        except Exception as e:
            st.error(f"Erro ao ler o arquivo: {e}")
            return

        df = validar_csv(df)
        if df is None:
            return

        df["semana"] = df["data"].dt.isocalendar().week.astype(int)
        df["faturamento"] = df["quantidade"] * df["preco"]

        st.subheader("Prévia dos dados")
        st.dataframe(df)

        total_vendido = df["quantidade"].sum()
        total_faturado = df["faturamento"].sum()
        total_produtos = df["produto"].nunique()

        c1, c2, c3 = st.columns(3)
        c1.metric("Total vendido", int(total_vendido))
        c2.metric("Faturamento total", f"R$ {total_faturado:,.2f}")
        c3.metric("Produtos diferentes", int(total_produtos))

        st.subheader("Produtos mais vendidos")
        mais_vendidos = df.groupby("produto")["quantidade"].sum().sort_values(ascending=False)
        st.dataframe(mais_vendidos.reset_index())

        fig1, ax1 = plt.subplots(figsize=(8, 4))
        mais_vendidos.plot(kind="bar", ax=ax1)
        ax1.set_title("Produtos mais vendidos")
        ax1.set_xlabel("Produto")
        ax1.set_ylabel("Quantidade")
        st.pyplot(fig1)

        st.subheader("Vendas por semana")
        vendas_semanais = df.groupby("semana")["quantidade"].sum()

        fig2, ax2 = plt.subplots(figsize=(8, 4))
        vendas_semanais.plot(marker="o", ax=ax2)
        ax2.set_title("Quantidade vendida por semana")
        ax2.set_xlabel("Semana")
        ax2.set_ylabel("Quantidade")
        ax2.grid(True)
        st.pyplot(fig2)

        st.subheader("Produto mais vendido por semana")
        top_por_semana = (
            df.groupby(["semana", "produto"])["quantidade"]
            .sum()
            .reset_index()
        )
        top_por_semana = top_por_semana.loc[top_por_semana.groupby("semana")["quantidade"].idxmax()]
        st.dataframe(top_por_semana)

        st.subheader("Sugestão de reposição de estoque")
        media_semanal = (
            df.groupby(["produto", "semana"])["quantidade"]
            .sum()
            .reset_index()
            .groupby("produto")["quantidade"]
            .mean()
            .reset_index()
        )
        media_semanal.columns = ["produto", "media_venda_semanal"]

        estoque_produto = df.groupby("produto")["estoque_atual"].last().reset_index()

        reposicao = pd.merge(media_semanal, estoque_produto, on="produto", how="left")
        reposicao["estoque_ideal"] = (reposicao["media_venda_semanal"] * 1.2).round()
        reposicao["quantidade_repor"] = (
            reposicao["estoque_ideal"] - reposicao["estoque_atual"]
        ).clip(lower=0).round()

        st.dataframe(reposicao.sort_values("quantidade_repor", ascending=False))

    else:
        st.info("Faça login e envie um arquivo CSV para começar.")

# -----------------------------
# FLUXO PRINCIPAL
# -----------------------------
if st.session_state.logado:
    dashboard()
else:
    tela_login()