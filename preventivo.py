import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error

# =========================================================
# 1. CARREGAR BASE DE DADOS
# =========================================================
try:
    df = pd.read_csv("vendas.csv")
    print("Base de dados carregada com sucesso.")
except FileNotFoundError:
    print("Arquivo 'vendas.csv' não encontrado.")
    exit()

# =========================================================
# 2. PRÉ-PROCESSAMENTO
# =========================================================
print("\nPrimeiras linhas da base:")
print(df.head())

# Converter data
df["data"] = pd.to_datetime(df["data"], errors="coerce")

# Remover linhas com dados essenciais ausentes
df = df.dropna(subset=["data", "produto", "quantidade", "preco"])

# Garantir tipos corretos
df["quantidade"] = pd.to_numeric(df["quantidade"], errors="coerce")
df["preco"] = pd.to_numeric(df["preco"], errors="coerce")

if "estoque_atual" in df.columns:
    df["estoque_atual"] = pd.to_numeric(df["estoque_atual"], errors="coerce")
else:
    df["estoque_atual"] = 0

df = df.dropna()

# Criar colunas auxiliares
df["ano"] = df["data"].dt.year
df["mes"] = df["data"].dt.month
df["dia"] = df["data"].dt.day
df["dia_semana"] = df["data"].dt.dayofweek
df["semana"] = df["data"].dt.isocalendar().week.astype(int)
df["faturamento"] = df["quantidade"] * df["preco"]

print("\nBase tratada com sucesso.")
print(df.info())

# =========================================================
# 3. ANÁLISE GERAL DE VENDAS
# =========================================================
print("\n=== PRODUTOS MAIS VENDIDOS NO PERÍODO ===")
mais_vendidos = df.groupby("produto")["quantidade"].sum().sort_values(ascending=False)
print(mais_vendidos)

print("\n=== FATURAMENTO POR PRODUTO ===")
faturamento_produto = df.groupby("produto")["faturamento"].sum().sort_values(ascending=False)
print(faturamento_produto)

# =========================================================
# 4. PRODUTOS MAIS VENDIDOS POR SEMANA
# =========================================================
print("\n=== PRODUTOS MAIS VENDIDOS POR SEMANA ===")
vendas_semanais = (
    df.groupby(["semana", "produto"])["quantidade"]
    .sum()
    .reset_index()
    .sort_values(["semana", "quantidade"], ascending=[True, False])
)
print(vendas_semanais.head(20))

# Produto mais vendido por semana
top_por_semana = vendas_semanais.loc[
    vendas_semanais.groupby("semana")["quantidade"].idxmax()
]
print("\n=== TOP PRODUTO DE CADA SEMANA ===")
print(top_por_semana)

# =========================================================
# 5. ANÁLISE TEMPORAL POR PRODUTO
# =========================================================
vendas_diarias = (
    df.groupby(["data", "produto"])["quantidade"]
    .sum()
    .reset_index()
    .sort_values("data")
)

print("\n=== VENDAS DIÁRIAS ===")
print(vendas_diarias.head())

# =========================================================
# 6. PREPARAÇÃO PARA MODELO PREDITIVO
# =========================================================
# Transformar produto em código numérico
vendas_diarias["produto_codigo"] = vendas_diarias["produto"].astype("category").cat.codes

# Criar variáveis de data
vendas_diarias["ano"] = vendas_diarias["data"].dt.year
vendas_diarias["mes"] = vendas_diarias["data"].dt.month
vendas_diarias["dia"] = vendas_diarias["data"].dt.day
vendas_diarias["dia_semana"] = vendas_diarias["data"].dt.dayofweek
vendas_diarias["semana"] = vendas_diarias["data"].dt.isocalendar().week.astype(int)

# Variáveis de entrada
X = vendas_diarias[["produto_codigo", "ano", "mes", "dia", "dia_semana", "semana"]]
y = vendas_diarias["quantidade"]

# Separação treino e teste
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# =========================================================
# 7. TREINAR MODELO
# =========================================================
modelo = RandomForestRegressor(n_estimators=100, random_state=42)
modelo.fit(X_train, y_train)

# Previsões
y_pred = modelo.predict(X_test)

# Métricas
mae = mean_absolute_error(y_test, y_pred)
rmse = np.sqrt(mean_squared_error(y_test, y_pred))

print("\n=== DESEMPENHO DO MODELO ===")
print(f"MAE: {mae:.2f}")
print(f"RMSE: {rmse:.2f}")

# =========================================================
# 8. PREVISÃO FUTURA SIMPLES
# =========================================================
# Exemplo: prever para uma data futura
data_futura = pd.to_datetime("2026-01-15")

produtos_unicos = vendas_diarias[["produto", "produto_codigo"]].drop_duplicates()

previsoes_futuras = []
for _, row in produtos_unicos.iterrows():
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

print("\n=== PREVISÃO DE VENDAS FUTURAS ===")
print(df_previsoes.sort_values("quantidade_prevista", ascending=False))

# =========================================================
# 9. SUGESTÃO DE REPOSIÇÃO DE ESTOQUE
# =========================================================
# Média semanal de vendas por produto
media_semanal = (
    df.groupby(["produto", "semana"])["quantidade"]
    .sum()
    .reset_index()
    .groupby("produto")["quantidade"]
    .mean()
    .reset_index()
)

media_semanal.columns = ["produto", "media_venda_semanal"]

# Estoque atual por produto
estoque_produto = (
    df.groupby("produto")["estoque_atual"]
    .last()
    .reset_index()
)

# Juntar informações
reposicao = pd.merge(media_semanal, estoque_produto, on="produto", how="left")

# Regra de estoque ideal: 20% acima da média semanal
reposicao["estoque_ideal"] = (reposicao["media_venda_semanal"] * 1.2).round()
reposicao["quantidade_repor"] = (
    reposicao["estoque_ideal"] - reposicao["estoque_atual"]
).clip(lower=0).round()

print("\n=== SUGESTÃO DE REPOSIÇÃO DE ESTOQUE ===")
print(reposicao.sort_values("quantidade_repor", ascending=False))

# =========================================================
# 10. GRÁFICOS
# =========================================================
# Top 10 produtos mais vendidos
plt.figure(figsize=(10, 5))
mais_vendidos.head(10).plot(kind="bar")
plt.title("Top 10 Produtos Mais Vendidos")
plt.xlabel("Produto")
plt.ylabel("Quantidade Vendida")
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()

# Vendas por semana
vendas_totais_semana = df.groupby("semana")["quantidade"].sum()

plt.figure(figsize=(10, 5))
vendas_totais_semana.plot(marker="o")
plt.title("Quantidade Vendida por Semana")
plt.xlabel("Semana")
plt.ylabel("Quantidade")
plt.grid(True)
plt.tight_layout()
plt.show()

# =========================================================
# 11. EXPORTAR RESULTADOS
# =========================================================.venv\Scripts\activate
mais_vendidos.to_csv("produtos_mais_vendidos.csv")
vendas_semanais.to_csv("vendas_por_semana.csv", index=False)
df_previsoes.to_csv("previsoes_futuras.csv", index=False)
reposicao.to_csv("reposicao_estoque.csv", index=False)

print("\nArquivos exportados com sucesso:")
print("- produtos_mais_vendidos.csv")
print("- vendas_por_semana.csv")
print("- previsoes_futuras.csv")
print("- reposicao_estoque.csv")