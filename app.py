import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

from preventivo import processar_dados
from relatorio import gerar_pdf
from recomendacoes import gerar_recomendacoes

st.set_page_config(
    page_title="Análise Preditiva + Análise Descritiva",
    page_icon="📊",
    layout="wide"
)


def carregar_css(nome_arquivo):
    with open(nome_arquivo, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


carregar_css("style.css")

USUARIO_CORRETO = "admin"
SENHA_CORRETA = "1234"

if "logado" not in st.session_state:
    st.session_state.logado = False


def tela_login():
    st.markdown('<div class="top-bar">Sistema Inteligente de Vendas</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-wrapper">', unsafe_allow_html=True)
    st.markdown('<div class="login-card">', unsafe_allow_html=True)
    st.markdown("<h1>Área de Login</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p class='subtitle'>Entre para acessar o dashboard de análise de vendas e estoque.</p>",
        unsafe_allow_html=True
    )

    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")

    if st.button("Entrar", use_container_width=True):
        if usuario == USUARIO_CORRETO and senha == SENHA_CORRETA:
            st.session_state.logado = True
            st.success("Login realizado com sucesso.")
            st.rerun()
        else:
            st.error("Usuário ou senha inválidos.")

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def botao_logout():
    st.sidebar.markdown("## Painel")
    if st.sidebar.button("Sair do sistema", use_container_width=True):
        st.session_state.logado = False
        st.rerun()


def dashboard():
    st.markdown('<div class="top-bar">Dashboard Inteligente de Vendas</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="info-box">Faça upload do arquivo CSV para gerar análise descritiva, previsão de vendas, sugestões de estoque e recomendações automáticas.</div>',
        unsafe_allow_html=True
    )

    botao_logout()

    st.sidebar.markdown("### Upload do arquivo")
    arquivo = st.sidebar.file_uploader("Selecione um arquivo CSV", type=["csv"])

    st.sidebar.markdown("### Formato esperado")
    st.sidebar.code(
        "data,produto,quantidade,preco,estoque_atual\n"
        "2025-01-01,Arroz,10,5.50,30\n"
        "2025-01-01,Feijao,8,7.00,20"
    )

    if arquivo is None:
        st.info("Envie um arquivo CSV pela barra lateral para começar.")
        return

    try:
        df = pd.read_csv(arquivo)
    except Exception as e:
        st.error(f"Erro ao ler o arquivo: {e}")
        return

    resultado = processar_dados(df)

    if not resultado["sucesso"]:
        st.error(resultado["erro"])
        return

    if resultado.get("colunas_reconhecidas"):
        st.info(
            f"Colunas reconhecidas automaticamente: {resultado['colunas_reconhecidas']}"
        )

    if resultado.get("faltantes"):
        st.warning(
            f"O sistema adaptou automaticamente as colunas faltantes: {resultado['faltantes']}"
        )

    df_limpo = resultado["df_limpo"]
    mae = resultado["mae"]
    rmse = resultado["rmse"]

    # Filtro de período
    data_min = df_limpo["data"].min().date()
    data_max = df_limpo["data"].max().date()

    intervalo_datas = st.sidebar.date_input(
        "Filtrar por período",
        value=(data_min, data_max),
        min_value=data_min,
        max_value=data_max
    )

    if isinstance(intervalo_datas, tuple) and len(intervalo_datas) == 2:
        data_inicial, data_final = intervalo_datas
    else:
        data_inicial = data_min
        data_final = data_max

    # Filtra primeiro por data
    df_filtrado = df_limpo[
        (df_limpo["data"].dt.date >= data_inicial) &
        (df_limpo["data"].dt.date <= data_final)
    ].copy()

    produtos = ["Todos"] + sorted(df_filtrado["produto"].unique().tolist()) if not df_filtrado.empty else ["Todos"]
    produto_escolhido = st.sidebar.selectbox("Filtrar produto", produtos)

    # Depois filtra por produto
    if produto_escolhido != "Todos":
        df_filtrado = df_filtrado[df_filtrado["produto"] == produto_escolhido].copy()

    if df_filtrado.empty:
        st.warning("Nenhum dado encontrado para o período ou filtro selecionado.")
        return

    st.info(
        f"Período selecionado: {data_inicial.strftime('%d/%m/%Y')} até {data_final.strftime('%d/%m/%Y')}"
    )

    # Recalcular tudo com base no filtro aplicado
    mais_vendidos = df_filtrado.groupby("produto")["quantidade"].sum().sort_values(ascending=False)

    faturamento_produto = (
        df_filtrado.groupby("produto")["faturamento"]
        .sum()
        .sort_values(ascending=False)
    )

    vendas_semanais = (
        df_filtrado.groupby(["semana", "produto"])["quantidade"]
        .sum()
        .reset_index()
        .sort_values(["semana", "quantidade"], ascending=[True, False])
    )

    top_por_semana = vendas_semanais.loc[
        vendas_semanais.groupby("semana")["quantidade"].idxmax()
    ] if not vendas_semanais.empty else pd.DataFrame(columns=["semana", "produto", "quantidade"])

    reposicao = (
        df_filtrado.groupby(["produto", "semana"])["quantidade"]
        .sum()
        .reset_index()
        .groupby("produto")["quantidade"]
        .mean()
        .reset_index()
    )
    reposicao.columns = ["produto", "media_venda_semanal"]

    estoque_produto = (
        df_filtrado.groupby("produto")["estoque_atual"]
        .last()
        .reset_index()
    )

    reposicao = pd.merge(reposicao, estoque_produto, on="produto", how="left")
    reposicao["estoque_ideal"] = (reposicao["media_venda_semanal"] * 1.2).round()
    reposicao["quantidade_repor"] = (
        reposicao["estoque_ideal"] - reposicao["estoque_atual"]
    ).clip(lower=0).round()
    reposicao = reposicao.sort_values("quantidade_repor", ascending=False)

    df_previsoes = resultado["df_previsoes"]
    if produto_escolhido != "Todos":
        df_previsoes = df_previsoes[df_previsoes["produto"] == produto_escolhido]

    recomendacoes = gerar_recomendacoes(
        df_filtrado,
        reposicao,
        mais_vendidos
    )

    total_vendido = int(df_filtrado["quantidade"].sum())
    total_faturado = float(df_filtrado["faturamento"].sum())
    total_produtos = int(df_filtrado["produto"].nunique())
    estoque_medio = float(df_filtrado["estoque_atual"].mean())

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total vendido", f"{total_vendido}")
    with c2:
        st.metric("Faturamento", f"R$ {total_faturado:,.2f}")
    with c3:
        st.metric("Produtos únicos", f"{total_produtos}")
    with c4:
        st.metric("Estoque médio", f"{estoque_medio:.1f}")

    st.subheader("Gerar relatório em PDF")

    tabela_pdf = mais_vendidos.reset_index()

    pdf = gerar_pdf(
        total_vendido=total_vendido,
        total_faturado=total_faturado,
        top_produtos=tabela_pdf
    )

    st.download_button(
        label="Baixar relatório em PDF",
        data=pdf,
        file_name="relatorio_vendas.pdf",
        mime="application/pdf"
    )

    aba1, aba2, aba3, aba4, aba5, aba6 = st.tabs(
        ["Base", "Análise Geral", "Semanal", "Previsão", "Estoque", "Recomendações"]
    )

    with aba1:
        st.subheader("Prévia dos dados")
        st.dataframe(df_filtrado, use_container_width=True)

    with aba2:
        st.subheader("Produtos mais vendidos")

        tabela_mais_vendidos = mais_vendidos.reset_index()
        tabela_faturamento = faturamento_produto.reset_index()

        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown("### Ranking por quantidade")
            st.dataframe(tabela_mais_vendidos, use_container_width=True)

            fig1, ax1 = plt.subplots(figsize=(8, 4))
            tabela_mais_vendidos.set_index("produto")["quantidade"].plot(kind="bar", ax=ax1)
            ax1.set_title("Produtos mais vendidos")
            ax1.set_xlabel("Produto")
            ax1.set_ylabel("Quantidade")
            plt.xticks(rotation=45)
            plt.tight_layout()
            st.pyplot(fig1)

        with col_b:
            st.markdown("### Ranking por faturamento")
            st.dataframe(tabela_faturamento, use_container_width=True)

            fig2, ax2 = plt.subplots(figsize=(8, 4))
            tabela_faturamento.set_index("produto")["faturamento"].plot(kind="bar", ax=ax2)
            ax2.set_title("Faturamento por produto")
            ax2.set_xlabel("Produto")
            ax2.set_ylabel("Faturamento")
            plt.xticks(rotation=45)
            plt.tight_layout()
            st.pyplot(fig2)

    with aba3:
        st.subheader("Produtos mais vendidos por semana")

        st.dataframe(top_por_semana, use_container_width=True)

        vendas_por_semana = df_filtrado.groupby("semana")["quantidade"].sum()

        fig3, ax3 = plt.subplots(figsize=(10, 4))
        vendas_por_semana.plot(marker="o", ax=ax3)
        ax3.set_title("Quantidade vendida por semana")
        ax3.set_xlabel("Semana")
        ax3.set_ylabel("Quantidade")
        ax3.grid(True)
        plt.tight_layout()
        st.pyplot(fig3)

    with aba4:
        st.subheader("Previsão de vendas futuras")

        p1, p2 = st.columns(2)
        with p1:
            st.metric("MAE", f"{mae:.2f}")
        with p2:
            st.metric("RMSE", f"{rmse:.2f}")

        st.dataframe(
            df_previsoes.sort_values("quantidade_prevista", ascending=False),
            use_container_width=True
        )

        if not df_previsoes.empty:
            fig4, ax4 = plt.subplots(figsize=(10, 4))
            df_previsoes.set_index("produto")["quantidade_prevista"].plot(kind="bar", ax=ax4)
            ax4.set_title("Quantidade prevista por produto")
            ax4.set_xlabel("Produto")
            ax4.set_ylabel("Quantidade prevista")
            plt.xticks(rotation=45)
            plt.tight_layout()
            st.pyplot(fig4)

    with aba5:
        st.subheader("Sugestão de reposição de estoque")

        st.dataframe(
            reposicao.sort_values("quantidade_repor", ascending=False),
            use_container_width=True
        )

        if not reposicao.empty:
            fig5, ax5 = plt.subplots(figsize=(10, 4))
            reposicao.set_index("produto")["quantidade_repor"].plot(kind="bar", ax=ax5)
            ax5.set_title("Quantidade sugerida para reposição")
            ax5.set_xlabel("Produto")
            ax5.set_ylabel("Quantidade")
            plt.xticks(rotation=45)
            plt.tight_layout()
            st.pyplot(fig5)

    with aba6:
        st.subheader("Área de Recomendações")

        if recomendacoes:
            for rec in recomendacoes:
                st.success(rec)
        else:
            st.info("Não foi possível gerar recomendações para os dados enviados.")


if st.session_state.logado:
    dashboard()
else:
    tela_login()
