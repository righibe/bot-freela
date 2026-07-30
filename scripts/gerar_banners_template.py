"""
Gera banners no estilo oficial do servidor usando o template em branco
(assets/referencias/PROGRAMADORES6.png) + fonte Poppins — a mesma identidade
visual dos banners profissionais (Suporte, Regras, Ranking...).

Rodar: python scripts/gerar_banners_template.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).parent.parent
TEMPLATE = RAIZ / 'assets' / 'referencias' / 'PROGRAMADORES6.png'
BANNERS = RAIZ / 'assets' / 'banners'
FONTS = RAIZ / 'assets' / 'fonts'

POPPINS_EXTRABOLD = str(FONTS / 'Poppins-ExtraBold.ttf')
POPPINS_MEDIUM = str(FONTS / 'Poppins-Medium.ttf')

FONTE_EMOJI = 'C:/Windows/Fonts/seguiemj.ttf'

# nome_arquivo: (título, subtítulo, [(emoji, tamanho, x_frac, y_frac, rotação), ...])
BANNERS_GERAR = {
    'comece': ('Bem-vindo', 'O seu lugar é aqui!', [
        ('👋', 150, 0.86, 0.20, -18), ('🚀', 110, 0.10, 0.16, 15), ('💸', 95, 0.90, 0.80, 12),
    ]),
    'termos': ('Termos', 'Leia e aceite para desbloquear o servidor', [
        ('📜', 150, 0.87, 0.22, 14), ('⚖️', 105, 0.09, 0.18, -12), ('🔏', 90, 0.90, 0.82, -10),
    ]),
    'dev': ('Verificação', 'Prove sua stack e comece a faturar', [
        ('💻', 145, 0.88, 0.22, -14), ('⚡', 105, 0.08, 0.16, 12), ('🐍', 90, 0.91, 0.82, 18),
    ]),
    'emp': ('Projetos', 'Contrate devs verificados', [
        ('💼', 145, 0.87, 0.20, 12), ('📋', 100, 0.09, 0.17, -14), ('💰', 95, 0.90, 0.82, -12),
    ]),
    'sugestao': ('Sugestões', 'Sua tecnologia não está aqui? Sugira!', [
        ('💡', 145, 0.88, 0.20, -12), ('🧩', 100, 0.08, 0.16, 15), ('⭐', 90, 0.90, 0.82, 14),
    ]),
}


def _texto_espacado_centralizado(draw, centro_x, y, texto, font, fill, tracking=5):
    """Desenha texto com tracking, centralizado horizontalmente em centro_x."""
    largura_total = sum(draw.textlength(ch, font=font) + tracking for ch in texto) - tracking
    x = centro_x - largura_total / 2
    for ch in texto:
        draw.text((x, y), ch, font=font, fill=fill, anchor='lm')
        x += draw.textlength(ch, font=font) + tracking


def _colar_emoji(img: Image.Image, emoji: str, tamanho: int, x_frac: float, y_frac: float, rotacao: float):
    """Renderiza um emoji rotacionado e cola no banner (imitando os objetos 3D)."""
    lado = tamanho + 40
    camada = Image.new('RGBA', (lado, lado), (0, 0, 0, 0))
    d = ImageDraw.Draw(camada)
    f = ImageFont.truetype(FONTE_EMOJI, tamanho)
    d.text((lado // 2, lado // 2), emoji, font=f, embedded_color=True, anchor='mm')
    camada = camada.rotate(rotacao, expand=True, resample=Image.BICUBIC)
    x = int(img.width * x_frac - camada.width / 2)
    y = int(img.height * y_frac - camada.height / 2)
    img.alpha_composite(camada, (x, y))


def gerar(nome: str, titulo: str, subtitulo: str, emojis: list) -> None:
    img = Image.open(TEMPLATE).convert('RGBA')
    W, H = img.size  # 1024x500

    # Emojis decorativos primeiro (ficam atrás do texto)
    for emoji, tamanho, xf, yf, rot in emojis:
        _colar_emoji(img, emoji, tamanho, xf, yf, rot)

    d = ImageDraw.Draw(img)
    centro_x = W // 2

    # Título: Poppins ExtraBold, branco, CENTRALIZADO, encolhe até caber
    tamanho = 128
    f_titulo = ImageFont.truetype(POPPINS_EXTRABOLD, tamanho)
    while d.textlength(titulo, font=f_titulo) > (W - 200) and tamanho > 60:
        tamanho -= 4
        f_titulo = ImageFont.truetype(POPPINS_EXTRABOLD, tamanho)

    y_titulo = int(H * 0.52)
    d.text((centro_x, y_titulo), titulo, font=f_titulo, fill=(255, 255, 255), anchor='mm')

    # Subtítulo com tracking, centralizado acima do título
    f_sub = ImageFont.truetype(POPPINS_MEDIUM, 26)
    y_sub = y_titulo - int(tamanho * 0.62) - 16
    _texto_espacado_centralizado(d, centro_x, y_sub, subtitulo, f_sub, (240, 240, 240))

    img.convert('RGB').save(BANNERS / f'{nome}.png')
    print(f'banner {nome}.png ok ({titulo})')


if __name__ == '__main__':
    for nome, (titulo, subtitulo, emojis) in BANNERS_GERAR.items():
        gerar(nome, titulo, subtitulo, emojis)
    print('\nBanners no estilo oficial gerados em assets/banners/')
