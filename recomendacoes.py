import pandas as pd

def gerar_recomendacoes(df_limpo, reposicao, mais_vendidos):
    recomendacoes = []

    if df_limpo is None or df_limpo.empty:
        return recomendacoes

    # Período analisado
    data_min = df_limpo["data"].min()
    data_max = df_limpo["data"].max()

    if pd.notnull(data_min) and pd.notnull(data_max):
        recomendacoes.append(
            f"Período analisado: {data_min.strftime('%d/%m/%Y')} até {data_max.strftime('%d/%m/%Y')}."
        )

    # Produtos mais vendidos
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

    # Reposição de estoque
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

        baixo_giro = reposicao[reposicao["quantidade_repor"] == 0]
        if not baixo_giro.empty:
            produto_estavel = baixo_giro.iloc[0]["produto"]
            recomendacoes.append(
                f"O produto {produto_estavel} apresenta nível de estoque adequado no momento."
            )

    # Faturamento
    faturamento_total = df_limpo["faturamento"].sum()
    if faturamento_total > 0:
        recomendacoes.append(
            f"O faturamento total no período foi de R$ {faturamento_total:,.2f}."
        )

    # Produto com maior faturamento
    faturamento_produto = (
        df_limpo.groupby("produto")["faturamento"]
        .sum()
        .sort_values(ascending=False)
    )

    if not faturamento_produto.empty:
        produto_top_faturamento = faturamento_produto.index[0]
        valor_top = float(faturamento_produto.iloc[0])

        recomendacoes.append(
            f"O produto com maior contribuição para o faturamento foi {produto_top_faturamento}, totalizando R$ {valor_top:,.2f}."
        )

    # Média de vendas
    media_vendas = (
        df_limpo.groupby("produto")["quantidade"]
        .mean()
        .sort_values(ascending=False)
    )

    if not media_vendas.empty:
        produto_media = media_vendas.index[0]
        media_valor = float(media_vendas.iloc[0])

        recomendacoes.append(
            f"O produto {produto_media} apresentou a maior média de vendas por registro, com {media_valor:.2f} unidades."
        )

    return recomendacoes
