def gerar_recomendacoes(df_limpo, reposicao, mais_vendidos):
    recomendacoes = []

    if mais_vendidos is not None and not mais_vendidos.empty:
        produto_top = mais_vendidos.index[0]
        qtd_top = int(mais_vendidos.iloc[0])
        recomendacoes.append(
            f"O produto mais vendido no período foi {produto_top}, com {qtd_top} unidades vendidas."
        )

    if reposicao is not None and not reposicao.empty:
        urgente = reposicao[reposicao["quantidade_repor"] > 0]

        if not urgente.empty:
            top_urgente = urgente.sort_values("quantidade_repor", ascending=False).iloc[0]
            recomendacoes.append(
                f"Recomenda-se repor com urgência o produto {top_urgente['produto']}, "
                f"com necessidade estimada de {int(top_urgente['quantidade_repor'])} unidades."
            )
        else:
            recomendacoes.append(
                "Nenhum produto apresenta necessidade imediata de reposição."
            )

        baixo_giro = reposicao[reposicao["quantidade_repor"] == 0]
        if not baixo_giro.empty:
            produto_baixo = baixo_giro.iloc[0]["produto"]
            recomendacoes.append(
                f"O produto {produto_baixo} apresenta baixa necessidade de reposição no momento."
            )

    if df_limpo is not None and not df_limpo.empty:
        faturamento_total = df_limpo["faturamento"].sum()
        if faturamento_total > 0:
            recomendacoes.append(
                f"O período analisado gerou faturamento total de R$ {faturamento_total:,.2f}, "
                "indicando potencial para decisões estratégicas de compra e estoque."
            )

    return recomendacoes
