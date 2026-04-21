import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error


def validar_csv(df):
    df = df.copy()

    faltantes = []

    # DATA
    if "data" not in df.columns:
        df["data"] = pd.date_range(start="2025-01-01", periods=len(df))
        faltantes.append("data")
    else:
        df["data"] = pd.to_datetime(df["data"], errors="coerce")

    # PRODUTO
    if "produto" not in df.columns:
        df["produto"] = "Produto Genérico"
        faltantes.append("produto")

    # QUANTIDADE
    if "quantidade" not in df.columns:
        df["quantidade"] = 1
        faltantes.append("quantidade")
    else:
        df["quantidade"] = pd.to_numeric(df["quantidade"], errors="coerce").fillna(1)

    # PREÇO
    if "preco" not in df.columns:
        df["preco"] = 0
        faltantes.append("preco")
    else:
        df["preco"] = pd.to_numeric(df["preco"], errors="coerce").fillna(0)

    # ESTOQUE
    if "estoque_atual" not in df.columns:
        df["estoque_atual"] = 0
        faltantes.append("estoque_atual")
    else:
        df["estoque_atual"] = pd.to_numeric(df["estoque_atual"], errors="coerce").fillna(0)

    df = df.dropna(subset=["data"])

    return df, faltantes

def processar_dados(df):
    df, faltantes = validar_csv(df)

if df is None:
    return {
        "sucesso": False,
        "erro": "Erro ao processar arquivo"
    }

    try:
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
            "erro": f"Erro ao processar os dados: {e}"
        }
