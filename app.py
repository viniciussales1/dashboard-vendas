import re
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

from preventivo import processar_dados
from relatorio import gerar_pdf

st.set_page_config(
    page_title="Análise Preditiva + Análise Descritiva",
    page_icon="https://www.nubusnatal.com.br/imagens/estacionatal.png",
    layout="wide"
)


def carregar_css(nome_arquivo):
    with open(nome_arquivo, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


carregar_css("style.css")

USUARIO_CORRETO = "admin"
SENHA_CORRETA = "1234"
LIMITE_ARQUIVO_MB = 100
LIMITE_ARQUIVO_BYTES = LIMITE_ARQUIVO_MB * 1024 * 1024

if "logado" not in st.session_state:
    st.session_state.logado = False


def normalizar_nome_coluna(nome):
    nome = str(nome).strip().lower()
    nome = nome.replace("ç", "c")
    nome = nome.replace("ã", "a").replace("á", "a").replace("à", "a").replace("â", "a")
    nome = nome.replace("é", "e").replace("ê", "e")
    nome = nome.replace("í", "i")
    nome = nome.replace("ó", "o").replace("ô", "o").replace("õ", "o")
    nome = nome.replace("ú", "u")
    nome = re.sub(r"[^a-z0-9]+", "_", nome)
    nome = re.sub(r"_+", "_", nome).strip("_")
    return nome


def reconhecer_colunas(chunk):
    mapa_sinonimos = {
        "data": [
            "data", "dt", "dia", "data_venda", "dt_venda", "data_da_venda",
            "data_movimento", "data_pedido", "date"
        ],
        "produto": [
            "produto", "item", "nome_produto", "descricao", "descricao_produto",
            "produto_nome", "mercadoria", "product", "nome", "name", "name_product"
        ],
        "quantidade": [
            "quantidade", "qtd", "quant", "qte", "quantidade_vendida",
            "qtde", "units", "unidades", "volume"
        ],
        "preco": [
            "preco", "preco_unitario", "valor", "valor_unitario",
            "preco_venda", "price", "unit_price", "precounitario"
        ],
        "estoque_atual": [
            "estoque_atual", "estoque", "saldo_estoque", "qtd_estoque",
            "estoque_disponivel", "inventory", "stock"
        ]
    }

    colunas_originais = list(chunk.columns)
    colunas_normalizadas = {col: normalizar_nome_coluna(col) for col in colunas_originais}

    renomear = {}
    encontradas = {}

    for coluna_padrao, sinonimos in mapa_sinonimos.items():
        for original, normalizada in colunas_normalizadas.items():
            if normalizada == coluna_padrao or normalizada in sinonimos:
                renomear[original] = coluna_padrao
                encontradas[coluna_padrao] = original
                break

    chunk = chunk.rename(columns=renomear)
    return chunk, encontradas


def preparar_chunk(chunk):
    chunk = chunk.copy()
    chunk, encontradas = reconhecer_colunas(chunk)
    faltantes = []

    if "data" not in chunk.columns:
        chunk["data"] = pd.date_range(start="2025-01-01", periods=len(chunk))
        faltantes.append("data")
    else:
        chunk["data"] = pd.to_datetime(chunk["data"], errors="coerce")

    if "produto" not in chunk.columns:
        chunk["produto"] = "Produto Genérico"
        faltantes.append("produto")

    if "quantidade" not in chunk.columns:
        chunk["quantidade"] = 1
        faltantes.append("quantidade")
    else:
        chunk["quantidade"] = pd.to_numeric(chunk["quantidade"], errors="coerce").fillna(1)

    if "preco" not in chunk.columns:
        chunk["preco"] = 0
        faltantes.append("preco")
    else:
        chunk["preco"] = pd.to_numeric(chunk["preco"], errors="coerce").fillna(0)

    if "estoque_atual" not in chunk.columns:
        chunk["estoque_atual"] = 0
        faltantes.append("estoque_atual")
    else:
        chunk["estoque_atual"] = pd.to_numeric(chunk["estoque_atual"], errors="coerce").fillna(0)

    chunk = chunk.dropna(subset=["data"])
    return chunk, faltantes, encontradas


def acumular_series(dicionario, serie):
    for chave, valor in serie.items():
        dicionario[chave] = dicionario.get(chave, 0) + valor


def atualizar_progresso(progress_bar, status_text, percentual, mensagem):
    percentual = max(0, min(100, int(percentual)))
    progress_bar.progress(percentual)
    status_text.markdown(f"**{mensagem}** ({percentual}%)")


def primeira_passagem_metadata(
    arquivo,
    chunksize=100_000,
    total_bytes=None,
    progress_bar=None,
    status_text=None
):
    arquivo.seek(0)

    data_min = None
    data_max = None
    produtos = set()
    colunas_reconhecidas = {}
    faltantes = set()

    if progress_bar and status_text:
        atualizar_progresso(progress_bar, status_text, 0, "Lendo metadados do arquivo")

    for chunk in pd.read_csv(arquivo, chunksize=chunksize):
        chunk, faltantes_chunk, reconhecidas_chunk = preparar_chunk(chunk)

        for k, v in reconhecidas_chunk.items():
            if k not in colunas_reconhecidas:
                colunas_reconhecidas[k] = v

        for item in faltantes_chunk:
            faltantes.add(item)

        if not chunk.empty:
            chunk_min = chunk["data"].min()
            chunk_max = chunk["data"].max()

            if data_min is None or chunk_min < data_min:
                data_min = chunk_min
            if data_max is None or chunk_max > data_max:
                data_max = chunk_max

            produtos.update(chunk["produto"].dropna().unique().tolist())

        if total_bytes and progress_bar and status_text:
            lido = arquivo.tell()
            percentual = (lido / total_bytes) * 100
            atualizar_progresso(progress_bar, status_text, percentual, "Lendo metadados do arquivo")

    arquivo.seek(0)

    if progress_bar and status_text:
        atualizar_progresso(progress_bar, status_text, 100, "Metadados carregados")

    return {
        "data_min": data_min,
        "data_max": data_max,
        "produtos": sorted(produtos),
        "colunas_reconhecidas": colunas_reconhecidas,
        "faltantes": sorted(faltantes)
    }


def processar_em_chunks(
    arquivo,
    data_inicial,
    data_final,
    produto_escolhido,
    chunksize=100_000,
    limite_amostra_ml=200_000,
    total_bytes=None,
    progress_bar=None,
    status_text=None
):
    arquivo.seek(0)

    total_vendido = 0
    total_faturado = 0.0
    quantidade_por_produto = {}
    faturamento_por_produto = {}
    quantidade_por_semana_produto = {}
    ultimo_estoque_por_produto = {}

    preview_partes = []
    preview_restante = 5000

    amostra_ml_partes = []
    amostra_ml_restante = limite_amostra_ml

    if progress_bar and status_text:
        atualizar_progresso(progress_bar, status_text, 0, "Processando dados do arquivo")

    for chunk in pd.read_csv(arquivo, chunksize=chunksize):
        chunk, _, _ = preparar_chunk(chunk)

        if chunk.empty:
            if total_bytes and progress_bar and status_text:
                lido = arquivo.tell()
                percentual = (lido / total_bytes) * 100
                atualizar_progresso(progress_bar, status_text, percentual, "Processando dados do arquivo")
            continue

        chunk["ano"] = chunk["data"].dt.year
        chunk["mes"] = chunk["data"].dt.month
        chunk["dia"] = chunk["data"].dt.day
        chunk["dia_semana"] = chunk["data"].dt.dayofweek
        chunk["semana"] = chunk["data"].dt.isocalendar().week.astype(int)
        chunk["faturamento"] = chunk["quantidade"] * chunk["preco"]

        chunk = chunk[
            (chunk["data"].dt.date >= data_inicial) &
            (chunk["data"].dt.date <= data_final)
        ]

        if produto_escolhido != "Todos":
            chunk = chunk[chunk["produto"] == produto_escolhido]

        if not chunk.empty:
            total_vendido += int(chunk["quantidade"].sum())
            total_faturado += float(chunk["faturamento"].sum())

            acumular_series(
                quantidade_por_produto,
                chunk.groupby("produto")["quantidade"].sum()
            )

            acumular_series(
                faturamento_por_produto,
                chunk.groupby("produto")["faturamento"].sum()
            )

            acumular_series(
                quantidade_por_semana_produto,
                chunk.groupby(["semana", "produto"])["quantidade"].sum()
            )

            estoque_chunk = chunk.groupby("produto")["estoque_atual"].last()
            for produto, estoque in estoque_chunk.items():
                ultimo_estoque_por_produto[produto] = estoque

            if preview_restante > 0:
                parte_preview = chunk.head(preview_restante)
                preview_partes.append(parte_preview)
                preview_restante -= len(parte_preview)

            if amostra_ml_restante > 0:
                parte_amostra = chunk.head(amostra_ml_restante)
                amostra_ml_partes.append(parte_amostra)
                amostra_ml_restante -= len(parte_amostra)

        if total_bytes and progress_bar and status_text:
            lido = arquivo.tell()
            percentual = (lido / total_bytes) * 100
            atualizar_progresso(progress_bar, status_text, percentual, "Processando dados do arquivo")

    arquivo.seek(0)

    if progress_bar and status_text:
        atualizar_progresso(progress_bar, status_text, 100, "Processamento concluído")

    df_preview = pd.concat(preview_partes, ignore_index=True) if preview_partes else pd.DataFrame()
    df_amostra_ml = pd.concat(amostra_ml_partes, ignore_index=True) if amostra_ml_partes else pd.DataFrame()

    mais_vendidos = (
        pd.Series(quantidade_por_produto, dtype="float64")
        .sort_values(ascending=False)
        if quantidade_por_produto else pd.Series(dtype="float64")
    )

    faturamento_produto = (
        pd.Series(faturamento_por_produto, dtype="float64")
        .sort_values(ascending=False)
        if faturamento_por_produto else pd.Series(dtype="float64")
    )

    if quantidade_por_semana_produto:
        vendas_semanais = pd.DataFrame(
            [
                {"semana": semana, "produto": produto, "quantidade": quantidade}
                for (semana, produto), quantidade in quantidade_por_semana_produto.items()
            ]
        ).sort_values(["semana", "quantidade"], ascending=[True, False])
    else:
        vendas_semanais = pd.DataFrame(columns=["semana", "produto", "quantidade"])

    if not vendas_semanais.empty:
        top_por_semana = vendas_semanais.loc[
            vendas_semanais.groupby("semana")["quantidade"].idxmax()
        ]
    else:
        top_por_semana = pd.DataFrame(columns=["semana", "produto", "quantidade"])

    if not vendas_semanais.empty:
        media_semanal = (
            vendas_semanais.groupby("produto")["quantidade"]
            .mean()
            .reset_index()
        )
        media_semanal.columns = ["produto", "media_venda_semanal"]

        estoque_produto = pd.DataFrame(
            [{"produto": produto, "estoque_atual": estoque} for produto, estoque in ultimo_estoque_por_produto.items()]
        )

        reposicao = pd.merge(media_semanal, estoque_produto, on="produto", how="left")
        reposicao["estoque_ideal"] = (reposicao["media_venda_semanal"] * 1.2).round()
        reposicao["quantidade_repor"] = (
            reposicao["estoque_ideal"] - reposicao["estoque_atual"]
        ).clip(lower=0).round()
        reposicao = reposicao.sort_values("quantidade_repor", ascending=False)
    else:
        reposicao = pd.DataFrame(columns=["produto", "media_venda_semanal", "estoque_atual", "estoque_ideal", "quantidade_repor"])

    return {
        "df_preview": df_preview,
        "df_amostra_ml": df_amostra_ml,
        "mais_vendidos": mais_vendidos,
        "faturamento_produto": faturamento_produto,
        "vendas_semanais": vendas_semanais,
        "top_por_semana": top_por_semana,
        "reposicao": reposicao,
        "total_vendido": total_vendido,
        "total_faturado": total_faturado
    }


def gerar_recomendacoes_resumo(data_inicial, data_final, total_faturado, mais_vendidos, reposicao):
    recomendacoes = []

    recomendacoes.append(
        f"Período analisado: {data_inicial.strftime('%d/%m/%Y')} até {data_final.strftime('%d/%m/%Y')}."
    )

    if mais_vendidos is not None and not mais_vendidos.empty:
        produto_top = mais_vendidos.index[0]
        qtd_top = int(mais_vendidos.iloc[0])
        recomendacoes.append(
            f"O produto com maior volume de vendas foi {produto_top}, com {qtd_top} unidades."
        )

        if len(mais_vendidos) > 1:
            produto_segundo = mais_vendidos.index[1]
            qtd_segundo = int(mais_vendidos.iloc[1])
            recomendacoes.append(
                f"O segundo produto com maior volume de vendas foi {produto_segundo}, com {qtd_segundo} unidades."
            )

        produto_menos = mais_vendidos.index[-1]
        qtd_menos = int(mais_vendidos.iloc[-1])
        recomendacoes.append(
            f"O produto com menor volume de vendas foi {produto_menos}, com {qtd_menos} unidades."
        )

    if reposicao is not None and not reposicao.empty:
        urgente = reposicao[reposicao["quantidade_repor"] > 0]

        if not urgente.empty:
            urgente = urgente.sort_values("quantidade_repor", ascending=False)

            top_urgente = urgente.iloc[0]
            recomendacoes.append(
                f"Há necessidade de reposição do produto {top_urgente['produto']}, com estimativa de {int(top_urgente['quantidade_repor'])} unidades."
            )

            if len(urgente) > 1:
                segundo = urgente.iloc[1]
                recomendacoes.append(
                    f"O produto {segundo['produto']} também apresenta necessidade de reposição de aproximadamente {int(segundo['quantidade_repor'])} unidades."
                )

            recomendacoes.append(
                f"Foram identificados {len(urgente)} produtos com necessidade de reposição no período analisado."
            )
        else:
            recomendacoes.append(
                "Não foram identificadas necessidades imediatas de reposição de estoque."
            )

        estavel = reposicao[reposicao["quantidade_repor"] == 0]
        if not estavel.empty:
            produto_estavel = estavel.iloc[0]["produto"]
            recomendacoes.append(
                f"O produto {produto_estavel} apresenta nível de estoque adequado no momento."
            )

    if total_faturado > 0:
        recomendacoes.append(
            f"O faturamento total no período foi de R$ {total_faturado:,.2f}."
        )

    return recomendacoes


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
        '<div class="info-box">Faça upload do arquivo CSV para gerar análise descritiva completa, recomendações automáticas e previsão com amostragem controlada para melhor desempenho.</div>',
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

    tamanho_mb = arquivo.size / (1024 * 1024)
    if arquivo.size > LIMITE_ARQUIVO_BYTES:
        st.error(
            f"Arquivo muito grande ({tamanho_mb:.2f} MB). "
            f"O limite permitido é de {LIMITE_ARQUIVO_MB} MB."
        )
        return

    st.sidebar.success(f"Arquivo carregado: {tamanho_mb:.2f} MB / {LIMITE_ARQUIVO_MB} MB")

    progresso_metadata = st.progress(0)
    status_metadata = st.empty()

    try:
        metadata = primeira_passagem_metadata(
            arquivo=arquivo,
            chunksize=100_000,
            total_bytes=arquivo.size,
            progress_bar=progresso_metadata,
            status_text=status_metadata
        )
    except Exception as e:
        progresso_metadata.empty()
        status_metadata.empty()
        st.error(f"Erro ao ler o arquivo: {e}")
        return

    if metadata["colunas_reconhecidas"]:
        st.info(
            f"Colunas reconhecidas automaticamente: {metadata['colunas_reconhecidas']}"
        )

    if metadata["faltantes"]:
        st.warning(
            f"O sistema adaptou automaticamente as colunas faltantes: {metadata['faltantes']}"
        )

    if metadata["data_min"] is None or metadata["data_max"] is None:
        progresso_metadata.empty()
        status_metadata.empty()
        st.error("Não foi possível identificar dados válidos no arquivo.")
        return

    data_min = metadata["data_min"].date()
    data_max = metadata["data_max"].date()

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

    produtos = ["Todos"] + metadata["produtos"] if metadata["produtos"] else ["Todos"]
    produto_escolhido = st.sidebar.selectbox("Filtrar produto", produtos)

    progresso_processamento = st.progress(0)
    status_processamento = st.empty()

    try:
        resultado = processar_em_chunks(
            arquivo=arquivo,
            data_inicial=data_inicial,
            data_final=data_final,
            produto_escolhido=produto_escolhido,
            chunksize=100_000,
            limite_amostra_ml=200_000,
            total_bytes=arquivo.size,
            progress_bar=progresso_processamento,
            status_text=status_processamento
        )
    except Exception as e:
        progresso_processamento.empty()
        status_processamento.empty()
        st.error(f"Erro ao processar o arquivo: {e}")
        return

    progresso_metadata.empty()
    status_metadata.empty()
    progresso_processamento.empty()
    status_processamento.empty()

    df_preview = resultado["df_preview"]
    df_amostra_ml = resultado["df_amostra_ml"]
    mais_vendidos = resultado["mais_vendidos"]
    faturamento_produto = resultado["faturamento_produto"]
    vendas_semanais = resultado["vendas_semanais"]
    top_por_semana = resultado["top_por_semana"]
    reposicao = resultado["reposicao"]
    total_vendido = int(resultado["total_vendido"])
    total_faturado = float(resultado["total_faturado"])

    if total_vendido == 0 and total_faturado == 0 and df_preview.empty:
        st.warning("Nenhum dado encontrado para o período ou filtro selecionado.")
        return

    st.success("Arquivo processado com sucesso.")
    st.info(
        f"Período selecionado: {data_inicial.strftime('%d/%m/%Y')} até {data_final.strftime('%d/%m/%Y')}"
    )

    total_produtos = int(len(mais_vendidos))
    estoque_medio = float(df_preview["estoque_atual"].mean()) if not df_preview.empty else 0.0

    recomendacoes = gerar_recomendacoes_resumo(
        data_inicial=data_inicial,
        data_final=data_final,
        total_faturado=total_faturado,
        mais_vendidos=mais_vendidos,
        reposicao=reposicao
    )

    mae = 0.0
    rmse = 0.0
    df_previsoes = pd.DataFrame(columns=["produto", "data_previsao", "quantidade_prevista"])

    if not df_amostra_ml.empty:
        resultado_ml = processar_dados(df_amostra_ml)
        if resultado_ml["sucesso"]:
            mae = resultado_ml["mae"]
            rmse = resultado_ml["rmse"]
            df_previsoes = resultado_ml["df_previsoes"]

            if produto_escolhido != "Todos":
                df_previsoes = df_previsoes[df_previsoes["produto"] == produto_escolhido]

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
    tabela_pdf.columns = ["produto", "quantidade"]

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
        st.caption("A prévia exibe uma amostra das linhas filtradas. A análise foi feita com todas as linhas do arquivo.")
        st.dataframe(df_preview, use_container_width=True)

    with aba2:
        st.subheader("Produtos mais vendidos")

        tabela_mais_vendidos = mais_vendidos.reset_index()
        tabela_mais_vendidos.columns = ["produto", "quantidade"]

        tabela_faturamento = faturamento_produto.reset_index()
        tabela_faturamento.columns = ["produto", "faturamento"]

        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown("### Ranking por quantidade")
            st.dataframe(tabela_mais_vendidos, use_container_width=True)

            if not tabela_mais_vendidos.empty:
                fig1, ax1 = plt.subplots(figsize=(8, 4))
                tabela_mais_vendidos.set_index("produto")["quantidade"].head(20).plot(kind="bar", ax=ax1)
                ax1.set_title("Produtos mais vendidos")
                ax1.set_xlabel("Produto")
                ax1.set_ylabel("Quantidade")
                plt.xticks(rotation=45)
                plt.tight_layout()
                st.pyplot(fig1)

        with col_b:
            st.markdown("### Ranking por faturamento")
            st.dataframe(tabela_faturamento, use_container_width=True)

            if not tabela_faturamento.empty:
                fig2, ax2 = plt.subplots(figsize=(8, 4))
                tabela_faturamento.set_index("produto")["faturamento"].head(20).plot(kind="bar", ax=ax2)
                ax2.set_title("Faturamento por produto")
                ax2.set_xlabel("Produto")
                ax2.set_ylabel("Faturamento")
                plt.xticks(rotation=45)
                plt.tight_layout()
                st.pyplot(fig2)

    with aba3:
        st.subheader("Produtos mais vendidos por semana")

        st.dataframe(top_por_semana, use_container_width=True)

        vendas_por_semana = (
            vendas_semanais.groupby("semana")["quantidade"].sum()
            if not vendas_semanais.empty else pd.Series(dtype="float64")
        )

        if not vendas_por_semana.empty:
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
        st.caption("A previsão usa uma amostra controlada dos dados para manter o desempenho do ambiente web.")

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
