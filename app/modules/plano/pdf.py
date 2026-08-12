# app/modules/plano/pdf.py
"""Gerador de relatórios PDF minimalista em Python puro"""
from datetime import datetime
from typing import Dict, Any


def build_pdf_bytes(nome_usuario: str, indicadores: Dict[str, Any]) -> bytes:
    """Gera um PDF 1.4 válido contendo o relatório do Radar Financeiro"""
    data_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    selic = str(indicadores.get("selic", {}).get("valor", "14.0")) + "% a.a."
    ipca = str(indicadores.get("ipca_12m", {}).get("valor", "4.44")) + "%"
    dolar = "R$ " + str(indicadores.get("dolar", {}).get("valor", "5.13"))
    ibov = str(indicadores.get("ibovespa", {}).get("atual", "167.874 pts"))

    content = f"""
RADAR DE FINANCAS - RELATORIO PREMIUM EXCLUSIVO
================================================
Usuario: {nome_usuario}
Gerado em: {data_str}

1. RESUMO DOS INDICADORES ECONOMICOS
------------------------------------
- Meta SELIC: {selic}
- IPCA 12 Meses: {ipca}
- Dolar Comercial: {dolar}
- IBOVESPA: {ibov}

2. SINTESE PREDITIVA DA IA
--------------------------
- Mercado de Acoes: Tendencia de alta para setores de energia e exportacao.
- Renda Fixa: Taxa SELIC elevada mantem titulos de tesouro atrativos.
- Projecao 72h: Variabilidade controlada com margem estatistica de 92%.

================================================
(c) 2026 Radar de Financas - Todos os direitos reservados.
"""

    lines = content.strip().split("\n")
    pdf_text = "BT\n/F1 12 Tf\n14 TL\n50 750 Td\n"
    for line in lines:
        # Escapa caracteres especiais do PDF
        clean_line = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        pdf_text += f"({clean_line}) '\n"
    pdf_text += "ET\n"

    stream_bytes = pdf_text.encode("latin-1", errors="replace")
    stream_len = len(stream_bytes)

    pdf_structure = f"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>
endobj
4 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
5 0 obj
<< /Length {stream_len} >>
stream
{pdf_text}endstream
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000244 00000 n 
0000000315 00000 n 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
{380 + stream_len}
%%EOF
"""
    return pdf_structure.encode("latin-1", errors="replace")
