from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO


def gerar_pdf(total_vendido, total_faturado, top_produtos):
    buffer = BytesIO()

    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()

    elementos = []

    elementos.append(Paragraph("Relatório de Vendas", styles["Title"]))
    elementos.append(Spacer(1, 12))

    elementos.append(Paragraph(f"Total vendido: {total_vendido}", styles["Normal"]))
    elementos.append(Paragraph(f"Faturamento total: R$ {total_faturado:,.2f}", styles["Normal"]))

    elementos.append(Spacer(1, 12))
    elementos.append(Paragraph("Produtos mais vendidos:", styles["Heading2"]))

    for i, row in top_produtos.head(5).iterrows():
        elementos.append(
            
            Paragraph(f"{row['produto']} - {row['quantidade']}", styles["Normal"])
        )

    doc.build(elementos)

    buffer.seek(0)
    return buffer