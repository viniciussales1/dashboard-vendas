from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO
from datetime import datetime

elementos.append(
    Paragraph(f"Data do relatório: {datetime.now().strftime('%d/%m/%Y')}", styles["Normal"])
)


def gerar_pdf(total_vendido, total_faturado, top_produtos):
    buffer = BytesIO()

    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()

    elementos = []

    # TÍTULO
    elementos.append(Paragraph("<b>📊 RELATÓRIO DE VENDAS</b>", styles["Title"]))
    elementos.append(Spacer(1, 12))

    # RESUMO
    elementos.append(Paragraph(f"<b>Total vendido:</b> {total_vendido}", styles["Normal"]))
    elementos.append(Paragraph(f"<b>Faturamento total:</b> R$ {total_faturado:,.2f}", styles["Normal"]))
    elementos.append(Spacer(1, 20))

    # TABELA
    dados = [["Produto", "Quantidade"]]

    for _, row in top_produtos.head(10).iterrows():
        dados.append([row["produto"], row["quantidade"]])

    tabela = Table(dados)

    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),

        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),

        ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
        ("TOPPADDING", (0, 0), (-1, 0), 10),

        ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke),

        ("GRID", (0, 0), (-1, -1), 1, colors.grey)
    ]))

    elementos.append(Paragraph("<b>Top produtos mais vendidos</b>", styles["Heading2"]))
    elementos.append(Spacer(1, 10))
    elementos.append(tabela)

    elementos.append(Spacer(1, 20))

    # RODAPÉ
    elementos.append(Paragraph("Relatório gerado automaticamente pelo sistema.", styles["Italic"]))

    doc.build(elementos)

    buffer.seek(0)
    return buffer
