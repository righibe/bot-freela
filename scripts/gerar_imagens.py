"""
Gera as imagens do servidor (banners dos cards + avatares das personas).
Rodar uma vez: python scripts/gerar_imagens.py
Saída: assets/banners/*.png e assets/avatars/*.png
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

RAIZ = Path(__file__).parent.parent
BANNERS = RAIZ / 'assets' / 'banners'
AVATARS = RAIZ / 'assets' / 'avatars'
BANNERS.mkdir(parents=True, exist_ok=True)
AVATARS.mkdir(parents=True, exist_ok=True)

FONTE_TITULO = 'C:/Windows/Fonts/segoeuib.ttf'
FONTE_TEXTO = 'C:/Windows/Fonts/segoeui.ttf'
FONTE_EMOJI = 'C:/Windows/Fonts/seguiemj.ttf'

# tema: (cor_clara, cor_escura, emoji, título, subtítulo)
TEMAS = {
    'comece':  ((46, 204, 113), (8, 61, 34),   '👋', 'BEM-VINDO À FREEELA', 'trabalho + pagamento seguro via PIX'),
    'regras':  ((231, 76, 60),  (66, 8, 14),   '📕', 'REGRAS DO SERVIDOR', 'leia antes de participar'),
    'termos':  ((241, 196, 15), (82, 52, 4),   '📜', 'TERMOS DE USO', 'o contrato da plataforma'),
    # Nota: usar apenas emoji de codepoint único — sequências ZWJ (ex.: 🧑‍💻)
    # não renderizam como glifo único no Pillow sem libraqm.
    'dev':     ((52, 152, 219), (7, 33, 74),   '💻', 'VERIFICAÇÃO DEV', 'prove sua stack e comece a faturar'),
    'emp':     ((155, 89, 182), (39, 10, 66),  '🏢', 'PUBLIQUE SEU PROJETO', 'contrate devs verificados'),
    'perfil':  ((26, 188, 156), (5, 56, 50),   '🔄', 'ATUALIZAR PERFIL', 'novas linguagens e experiência'),
    'ticket':  ((230, 126, 34), (74, 33, 4),   '🎫', 'SUPORTE FREEELA', 'abra um ticket e fale com a staff'),
    'sugestao': ((190, 214, 48), (60, 70, 8),  '💡', 'SUGESTÕES', 'sua tecnologia não está aqui? sugira!'),
}


def gradiente(largura: int, altura: int, cor_a, cor_b, diagonal: bool = True) -> Image.Image:
    """Gradiente suave entre duas cores."""
    base = Image.new('RGB', (largura, altura))
    px = base.load()
    for y in range(altura):
        for x in range(0, largura, 4):
            t = ((x / largura) + (y / altura)) / 2 if diagonal else y / altura
            cor = tuple(int(a + (b - a) * t) for a, b in zip(cor_a, cor_b))
            for dx in range(4):
                if x + dx < largura:
                    px[x + dx, y] = cor
    return base


def _bolhas_decorativas(img: Image.Image, cor_clara) -> None:
    """Círculos translúcidos de decoração."""
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    w, h = img.size
    cor = (*cor_clara, 26)
    d.ellipse([w * 0.62, -h * 0.55, w * 1.12, h * 0.55], fill=cor)
    d.ellipse([w * 0.72, h * 0.5, w * 1.25, h * 1.6], fill=cor)
    d.ellipse([-w * 0.12, h * 0.62, w * 0.22, h * 1.35], fill=cor)
    img.paste(Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB'), (0, 0))


def gerar_banner(nome: str, tema) -> None:
    cor_clara, cor_escura, emoji, titulo, subtitulo = tema
    W, H = 1100, 340
    img = gradiente(W, H, cor_escura, cor_clara)
    _bolhas_decorativas(img, cor_clara)

    d = ImageDraw.Draw(img)

    # Faixa escura sutil na base
    faixa = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    fd = ImageDraw.Draw(faixa)
    fd.rectangle([0, H - 12, W, H], fill=(*cor_clara, 160))
    img.paste(Image.alpha_composite(img.convert('RGBA'), faixa).convert('RGB'), (0, 0))

    # Emoji grande à esquerda
    f_emoji = ImageFont.truetype(FONTE_EMOJI, 170)
    d = ImageDraw.Draw(img)
    d.text((70, H // 2), emoji, font=f_emoji, embedded_color=True, anchor='lm')

    # Título e subtítulo (fonte encolhe até caber na largura disponível)
    x_texto = 320
    largura_max = W - x_texto - 50
    tamanho = 76
    f_titulo = ImageFont.truetype(FONTE_TITULO, tamanho)
    while d.textlength(titulo, font=f_titulo) > largura_max and tamanho > 34:
        tamanho -= 2
        f_titulo = ImageFont.truetype(FONTE_TITULO, tamanho)
    f_sub = ImageFont.truetype(FONTE_TEXTO, 38)
    # sombra leve
    d.text((x_texto + 3, H // 2 - 32 + 3), titulo, font=f_titulo, fill=(0, 0, 0, 90), anchor='lm')
    d.text((x_texto, H // 2 - 32), titulo, font=f_titulo, fill=(255, 255, 255), anchor='lm')
    d.text((x_texto, H // 2 + 44), subtitulo, font=f_sub, fill=(235, 235, 235), anchor='lm')

    # Marca
    f_marca = ImageFont.truetype(FONTE_TITULO, 26)
    d.text((W - 40, H - 34), 'FREEELA', font=f_marca, fill=(255, 255, 255, 200), anchor='rm')

    img.save(BANNERS / f'{nome}.png')
    print(f'banner {nome}.png ok')


# Identidade visual dos avatares: ícone AZUL monocromático sobre fundo
# escuro discreto (nada de cores berrantes — o azul é o destaque).
AZUL_ICONE = (86, 130, 247)
FUNDO_ESCURO_TOPO = (7, 10, 18)
FUNDO_ESCURO_BASE = (13, 20, 38)


def _ruido(img: Image.Image, quantidade: int = 900, seed: int = 42) -> None:
    """Granulado sutil, como nos banners oficiais."""
    import random
    rng = random.Random(seed)
    px = img.load()
    w, h = img.size
    for _ in range(quantidade):
        x, y = rng.randrange(w), rng.randrange(h)
        r, g, b = px[x, y][:3]
        delta = rng.randint(8, 22)
        px[x, y] = (min(255, r + delta), min(255, g + delta), min(255, b + delta))


def _glow_radial(size: int, cor, raio_frac: float = 0.62, intensidade: int = 115) -> Image.Image:
    """Brilho radial suave (opaco no centro, transparente na borda) na cor dada."""
    glow = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    px = glow.load()
    centro = size / 2
    rmax = size * raio_frac
    for y in range(size):
        for x in range(size):
            dist = ((x - centro) ** 2 + (y - centro) ** 2) ** 0.5
            if dist < rmax:
                t = 1 - (dist / rmax)
                px[x, y] = (*cor, int(intensidade * (t ** 2)))
    return glow


def gerar_avatar(nome: str, tema) -> None:
    """
    Avatar da persona: emoji COLORIDO (com todo o detalhe) sobre o mesmo fundo
    escuro do bot, com um brilho na cor do tema e sombra suave para dar
    profundidade. Coeso com o avatar principal, mas cada canal reconhecível.
    """
    cor_clara, _cor_escura, emoji, *_ = tema
    S = 256

    # 1. Fundo escuro coeso com o bot principal + granulado sutil
    img = gradiente(S, S, FUNDO_ESCURO_TOPO, FUNDO_ESCURO_BASE, diagonal=False)
    _ruido(img)
    img = img.convert('RGBA')

    # 2. Brilho radial na cor do tema (dá identidade sem poluir)
    img.alpha_composite(_glow_radial(S, cor_clara))

    # 3. Emoji colorido, grande e centralizado
    f_emoji = ImageFont.truetype(FONTE_EMOJI, 150)
    glifo = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(glifo).text(
        (S // 2, S // 2), emoji, font=f_emoji, embedded_color=True, anchor='mm',
    )

    # 3a. Sombra suave a partir da silhueta do emoji (profundidade)
    sombra = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    sombra.putalpha(glifo.split()[3])
    sombra = sombra.filter(ImageFilter.GaussianBlur(7))
    img.alpha_composite(sombra, (0, 7))

    # 3b. Emoji por cima da sombra
    img.alpha_composite(glifo)

    # 4. Anel discreto na cor do tema
    d = ImageDraw.Draw(img)
    d.ellipse([6, 6, S - 6, S - 6], outline=(*cor_clara, 90), width=5)

    img.convert('RGB').save(AVATARS / f'{nome}.png')
    print(f'avatar {nome}.png ok')


def gerar_avatar_bot() -> None:
    """Avatar do bot principal: o logo </> azul sobre fundo escuro."""
    S = 256
    img = gradiente(S, S, FUNDO_ESCURO_TOPO, FUNDO_ESCURO_BASE, diagonal=False)
    _ruido(img)
    img = img.convert('RGBA')

    d = ImageDraw.Draw(img)
    fonts_dir = RAIZ / 'assets' / 'fonts'
    f_logo = ImageFont.truetype(str(fonts_dir / 'Poppins-ExtraBold.ttf'), 110)
    d.text((S // 2, S // 2 - 12), '</>', font=f_logo, fill=(*AZUL_ICONE, 255), anchor='mm')
    f_marca = ImageFont.truetype(str(fonts_dir / 'Poppins-Medium.ttf'), 28)
    d.text((S // 2, S // 2 + 66), 'FREEELA', font=f_marca, fill=(235, 240, 250, 255), anchor='mm')

    img.convert('RGB').save(AVATARS / 'bot.png')
    print('avatar bot.png ok')


if __name__ == '__main__':
    # ATENÇÃO: gera apenas os AVATARES. Os banners agora vêm do template
    # oficial do servidor (scripts/gerar_banners_template.py) e dos arquivos
    # profissionais em assets/referencias — não sobrescrever!
    for nome, tema in TEMAS.items():
        gerar_avatar(nome, tema)
    gerar_avatar_bot()
    print('\nAvatares gerados em assets/avatars/')
