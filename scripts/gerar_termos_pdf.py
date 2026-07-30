"""
Gera TERMOS_DE_USO.pdf a partir de TERMOS_DE_USO.md com layout profissional:
capa com identidade da plataforma, títulos de seção, tabela LGPD e rodapé
com numeração de páginas.

Rodar sempre que o .md mudar: python scripts/gerar_termos_pdf.py
"""

import re
from pathlib import Path

from fpdf import FPDF

RAIZ = Path(__file__).parent.parent
MD = RAIZ / 'TERMOS_DE_USO.md'
PDF_SAIDA = RAIZ / 'TERMOS_DE_USO.pdf'
FONTS = RAIZ / 'assets' / 'fonts'

AZUL = (37, 66, 133)
AZUL_CLARO = (52, 100, 190)
CINZA = (85, 85, 85)
PRETO = (25, 25, 30)


def limpar_markdown(texto: str) -> str:
    """Remove marcações markdown mantendo o texto."""
    texto = re.sub(r'\*\*(.+?)\*\*', r'\1', texto)
    texto = re.sub(r'\*(.+?)\*', r'\1', texto)
    texto = re.sub(r'`(.+?)`', r'\1', texto)
    texto = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', texto)
    return texto.strip()


class TermosPDF(FPDF):
    def __init__(self):
        super().__init__('P', 'mm', 'A4')
        self.add_font('Poppins', 'B', str(FONTS / 'Poppins-ExtraBold.ttf'))
        self.add_font('Poppins', '', str(FONTS / 'Poppins-Medium.ttf'))
        self.add_font('Segoe', '', 'C:/Windows/Fonts/segoeui.ttf')
        self.add_font('Segoe', 'B', 'C:/Windows/Fonts/segoeuib.ttf')
        self.add_font('Segoe', 'I', 'C:/Windows/Fonts/segoeuii.ttf')
        self.set_margins(20, 22, 20)
        self.set_auto_page_break(True, margin=24)

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font('Poppins', 'B', 9)
        self.set_text_color(*AZUL)
        self.cell(0, 6, 'FREEELA — TERMOS DE USO', align='L')
        self.set_font('Segoe', '', 8)
        self.set_text_color(*CINZA)
        self.cell(0, 6, 'Versão 1.0 • 10 de julho de 2026', align='R', new_x='LMARGIN', new_y='NEXT')
        self.set_draw_color(*AZUL_CLARO)
        self.set_line_width(0.4)
        self.line(20, self.get_y() + 1, 190, self.get_y() + 1)
        self.ln(6)

    def footer(self):
        self.set_y(-16)
        self.set_font('Segoe', '', 8)
        self.set_text_color(*CINZA)
        self.cell(0, 8, 'Plataforma Freeela • Intermediação de Serviços de Desenvolvimento de Software', align='L')
        self.cell(0, 8, f'Página {self.page_no()} de {{nb}}', align='R')

    # ── blocos ──
    def capa(self):
        self.add_page()
        self.set_fill_color(*AZUL)
        self.rect(0, 0, 210, 90, 'F')
        self.set_fill_color(*AZUL_CLARO)
        self.rect(0, 90, 210, 3, 'F')

        self.set_y(28)
        self.set_font('Poppins', 'B', 30)
        self.set_text_color(255, 255, 255)
        self.cell(0, 14, 'FREEELA', align='C', new_x='LMARGIN', new_y='NEXT')
        self.set_font('Poppins', '', 13)
        self.cell(0, 10, '</>  discord.gg/programador', align='C', new_x='LMARGIN', new_y='NEXT')

        self.set_y(110)
        self.set_font('Poppins', 'B', 22)
        self.set_text_color(*PRETO)
        self.cell(0, 12, 'TERMOS E CONDIÇÕES DE USO', align='C', new_x='LMARGIN', new_y='NEXT')
        self.set_font('Segoe', '', 12)
        self.set_text_color(*CINZA)
        self.cell(0, 9, 'Plataforma de intermediação de serviços de desenvolvimento de software',
                  align='C', new_x='LMARGIN', new_y='NEXT')
        self.ln(6)
        self.set_font('Poppins', 'B', 12)
        self.set_text_color(*AZUL)
        self.cell(0, 9, 'Versão 1.0 — vigente a partir de 10 de julho de 2026',
                  align='C', new_x='LMARGIN', new_y='NEXT')

        self.set_y(200)
        self.set_font('Segoe', 'I', 10)
        self.set_text_color(*CINZA)
        self.multi_cell(0, 6, (
            'O aceite eletrônico destes Termos, manifestado pelo botão "Li e Aceito" no servidor '
            'Discord da plataforma, é registrado com identificação do usuário, versão, data e hora '
            '(UTC), constituindo prova válida de manifestação de vontade nos termos do art. 107 do '
            'Código Civil brasileiro.'
        ), align='C')

    def secao(self, texto: str):
        if self.get_y() > 240:
            self.add_page()
        self.ln(4)
        self.set_font('Poppins', 'B', 13)
        self.set_text_color(*AZUL)
        self.multi_cell(0, 7, texto)
        self.set_draw_color(*AZUL_CLARO)
        self.set_line_width(0.3)
        self.line(20, self.get_y() + 0.5, 90, self.get_y() + 0.5)
        self.ln(3)

    def paragrafo(self, texto: str):
        self.set_font('Segoe', '', 10.5)
        self.set_text_color(*PRETO)
        self.multi_cell(0, 5.6, texto)
        self.ln(1.5)

    def citacao(self, texto: str):
        self.set_fill_color(238, 242, 252)
        self.set_font('Segoe', 'B', 10.5)
        self.set_text_color(*AZUL)
        self.multi_cell(0, 6, texto, fill=True)
        self.ln(2)

    def tabela(self, linhas: list[list[str]]):
        self.set_font('Segoe', 'B', 9)
        self.set_text_color(255, 255, 255)
        self.set_fill_color(*AZUL)
        larguras = [62, 62, 46]
        with self.table(
            col_widths=larguras, line_height=5.5,
            borders_layout='ALL', text_align='LEFT',
            padding=1.5,
        ) as tabela:
            for i, linha in enumerate(linhas):
                row = tabela.row()
                if i == 1:
                    self.set_font('Segoe', '', 8.5)
                    self.set_text_color(*PRETO)
                for celula in linha:
                    row.cell(celula)
        self.ln(3)


def gerar():
    conteudo = MD.read_text(encoding='utf-8')
    pdf = TermosPDF()
    pdf.capa()
    pdf.add_page()

    linhas = conteudo.splitlines()
    i = 0
    while i < len(linhas):
        linha = linhas[i].rstrip()

        if not linha or linha.startswith('# ') or linha == '---':
            i += 1
            continue

        if linha.startswith('**Versão'):
            i += 1
            continue

        if linha.startswith('## '):
            pdf.secao(limpar_markdown(linha[3:]))
            i += 1
            continue

        if linha.startswith('> '):
            bloco = []
            while i < len(linhas) and linhas[i].startswith('>'):
                bloco.append(limpar_markdown(linhas[i].lstrip('> ')))
                i += 1
            pdf.citacao(' '.join(b for b in bloco if b))
            continue

        if linha.startswith('|'):
            tabela = []
            while i < len(linhas) and linhas[i].startswith('|'):
                celulas = [limpar_markdown(c) for c in linhas[i].strip('|').split('|')]
                if not all(re.fullmatch(r'-+', c.strip()) for c in celulas if c.strip()):
                    tabela.append(celulas)
                i += 1
            if tabela:
                pdf.tabela(tabela)
            continue

        # Parágrafo comum (agrupa linhas contíguas)
        bloco = []
        while i < len(linhas) and linhas[i].strip() and not linhas[i].startswith(('#', '>', '|', '---')):
            bloco.append(limpar_markdown(linhas[i]))
            i += 1
        pdf.paragrafo('\n'.join(bloco))

    pdf.output(str(PDF_SAIDA))
    print(f'PDF gerado: {PDF_SAIDA} ({PDF_SAIDA.stat().st_size // 1024} KB, {pdf.page_no()} páginas)')


if __name__ == '__main__':
    gerar()
