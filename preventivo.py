import pandas as pd
import numpy as np
import re
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error


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


def reconhecer_colunas(df):
    mapa_sinonimos = {
        "data": [
            "data", "dt", "dia", "data_venda", "dt_venda", "data_da_venda",
            "data_movimento", "data_pedido", "date"
        ],
        "produto": [
            "produto", "item", "nome_produto", "descricao", "descricao_produto",
            "produto_nome", "mercadoria", "product", "nome"
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

    colunas_originais = list(df.columns)
    colunas_normalizadas = {col: normalizar_nome_coluna(col) for col in colunas_originais}

    renomear = {}
    encontradas = {}

    for coluna_padrao, sinonimos in mapa_sinonimos.items():
        for original, normalizada in colunas_normalizadas.items():
            if normalizada == coluna_padrao or normalizada in sinonimos:
                renomear[original] = coluna_padrao
                encontradas[coluna_padrao] = original
                break

    df = df.rename(columns=renomear)
    return df, encontradas


def validar_csv(df):
    df = df.copy()
    df, encontradas = reconhecer_colunas(df)
    faltantes = []

    if "data" not in df.columns:
        df["data"] = pd.date_range(start="2025-01-01", periods=len(df))
        faltantes.append("data")
    else:
        df["data"] = pd.to_datetime(df["data"], errors="coerce")

    if "produto" not in df.columns:
        df["produto"] = "Produto Genérico"
        faltantes.append("produto")

    if "quantidade" not in df.columns:
        df["quantidade"] = 1
        faltantes.append("quantidade")
    else:
        df["quantidade"] = pd.to_numeric(df["quantidade"], errors="coerce").fillna(1)

    if "preco" not in df.columns:
        df["preco"] = 0
        faltantes.append("preco")
    else:
        df["preco"] = pd.to_numeric(df["preco"], errors="coerce").fillna(0)

    if "estoque_atual" not in df.columns:
        df["estoque_atual"] = 0
        faltantes.append("estoque_atual")
    else:
        df["estoque_atual"] = pd.to_numeric(df["estoque_atual"], errors="coerce").fillna(0)

    df = df.dropna(subset=["data"])

    return df, faltantes, encontradas


def processar_dados(df):
    try:
        df, faltantes, encontradas = validar_csv(df)

        if df is None or df.empty:
            return {
                "sucesso": False,
                "erro": "Erro ao processar arquivo",
                "faltantes": faltantes if "faltantes" in locals() else [],
                "colunas_reconhecidas": encontradas if "encontradas" in locals() else {}
            }

        df["ano"] = df["data"].dt.year
        df["mes"] = df["data"].dt.month
        df["dia"] = df["data"].dt.day
        df["dia_semana"] = df["data"].dt.dayofweek
        df["semana"] = df["data"].dt.isocalendar().week.astype(int)
        df["faturamento"] = df["quantidade"] * df["preco"]

        mais_vendidos = df.groupby("produto")["quantidade"].sum().sort_values(ascending=False)

        faturamento_produto = (
            df.groupby("produto")["faturamento"]
            .sum()
            .sort_values(ascending=False)
        )

        vendas_semanais = (
            df.groupby(["semana", "produto"])["quantidade"]
            .sum()
            .reset_index()
            .sort_values(["semana", "quantidade"], ascending=[True, False])
        )

        top_por_semana = vendas_semanais.loc[
            vendas_semanais.groupby("semana")["quantidade"].idxmax()
        ]

        vendas_diarias = (
            df.groupby(["data", "produto"])["quantidade"]
            .sum()
            .reset_index()
            .sort_values("data")
        )

        vendas_diarias["produto_codigo"] = (
            vendas_diarias["produto"].astype("category").cat.codes
        )

        mapa_produtos = (
            vendas_diarias[["produto", "produto_codigo"]]
            .drop_duplicates()
            .sort_values("produto_codigo")
            .reset_index(drop=True)
        )

        vendas_diarias["ano"] = vendas_diarias["data"].dt.year
        vendas_diarias["mes"] = vendas_diarias["data"].dt.month
        vendas_diarias["dia"] = vendas_diarias["data"].dt.day
        vendas_diarias["dia_semana"] = vendas_diarias["data"].dt.dayofweek
        vendas_diarias["semana"] = vendas_diarias["data"].dt.isocalendar().week.astype(int)

        X = vendas_diarias[["produto_codigo", "ano", "mes", "dia", "dia_semana", "semana"]]
        y = vendas_diarias["quantidade"]

        if len(vendas_diarias) < 5:
            mae = 0.0
            rmse = 0.0
            df_previsoes = pd.DataFrame({
                "produto": mapa_produtos["produto"],
                "data_previsao": pd.to_datetime("2026-01-15"),
                "quantidade_prevista": 0
            })
        else:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )

            modelo = RandomForestRegressor(n_estimators=100, random_state=42)
            modelo.fit(X_train, y_train)

            y_pred = modelo.predict(X_test)

            mae = mean_absolute_error(y_test, y_pred)
            rmse = np.sqrt(mean_squared_error(y_test, y_pred))

            data_futura = pd.to_datetime("2026-01-15")
            previsoes_futuras = []

            for _, row in mapa_produtos.iterrows():
                entrada = pd.DataFrame([{
                    "produto_codigo": row["produto_codigo"],
                    "ano": data_futura.year,
                    "mes": data_futura.month,
                    "dia": data_futura.day,
                    "dia_semana": data_futura.dayofweek,
                    "semana": int(data_futura.isocalendar().week)
                }])

                previsao = modelo.predict(entrada)[0]

                previsoes_futuras.append({
                    "produto": row["produto"],
                    "data_previsao": data_futura,
                    "quantidade_prevista": max(0, round(previsao))
                })

            df_previsoes = pd.DataFrame(previsoes_futuras)

        media_semanal = (
            df.groupby(["produto", "semana"])["quantidade"]
            .sum()
            .reset_index()
            .groupby("produto")["quantidade"]
            .mean()
            .reset_index()
        )
        media_semanal.columns = ["produto", "media_venda_semanal"]

        estoque_produto = (
            df.groupby("produto")["estoque_atual"]
            .last()
            .reset_index()
        )

        reposicao = pd.merge(media_semanal, estoque_produto, on="produto", how="left")
        reposicao["estoque_ideal"] = (reposicao["media_venda_semanal"] * 1.2).round()
        reposicao["quantidade_repor"] = (
            reposicao["estoque_ideal"] - reposicao["estoque_atual"]
        ).clip(lower=0).round()

        reposicao = reposicao.sort_values("quantidade_repor", ascending=False)

        return {
            "sucesso": True,
            "erro": None,
            "faltantes": faltantes,
            "colunas_reconhecidas": encontradas,
            "df_limpo": df,
            "mais_vendidos": mais_vendidos,
            "faturamento_produto": faturamento_produto,
            "vendas_semanais": vendas_semanais,
            "top_por_semana": top_por_semana,
            "df_previsoes": df_previsoes,
            "reposicao": reposicao,
            "mae": mae,
            "rmse": rmse
        }

    except Exception as e:
        return {
            "sucesso": False,
            "erro": f"Erro ao processar os dados: {e}",
            "faltantes": [],
            "colunas_reconhecidas": {}
        }
