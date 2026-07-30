import re
import logging
from datetime import datetime, timezone
logger = logging.getLogger('bot_freeela.utils')

async def enviar_msg_erro_api(thread, user):
    import discord
    from config.settings import COR_ERRO, MSG_ERRO_API
    embed = discord.Embed(
        title='❌ Erro de Comunicação',
        description=MSG_ERRO_API,
        color=COR_ERRO
    )
    try:
        await thread.send(embed=embed)
    except:
        pass

def extrair_username_github(url_ou_user: str) -> str | None:
    url_ou_user = url_ou_user.strip().rstrip('/')
    padrao = re.compile('(?:https?://)?(?:www\\.)?github\\.com/([a-zA-Z0-9\\-]+)', re.IGNORECASE)
    match = padrao.search(url_ou_user)
    if match:
        return match.group(1)
    if '/' not in url_ou_user and ' ' not in url_ou_user:
        return url_ou_user
    return None

def extrair_username_linkedin(url_ou_user: str) -> str | None:
    url_ou_user = url_ou_user.strip().rstrip('/')
    padrao = re.compile('(?:https?://)?(?:www\\.)?linkedin\\.com/in/([a-zA-Z0-9\\-]+)', re.IGNORECASE)
    match = padrao.search(url_ou_user)
    if match:
        return match.group(1)
    if '/' not in url_ou_user and ' ' not in url_ou_user:
        return url_ou_user
    return None

def formatar_data(dt: datetime | None=None) -> str:
    if dt is None:
        dt = datetime.now(timezone.utc)
    return dt.strftime('%d/%m/%Y às %H:%M UTC')

def truncar_texto(texto: str, max_len: int=1024) -> str:
    if len(texto) <= max_len:
        return texto
    return texto[:max_len - 3] + '...'

def estimar_senioridade(experiencia: str, score_compat: int) -> str:
    mapa_base = {'6_meses': 'Iniciante', '1_ano': 'Júnior', '2_anos': 'Júnior avançado', '4_6_anos': 'Pleno', '6_mais': 'Pleno / Sênior'}
    base = mapa_base.get(experiencia, 'Não determinado')
    if score_compat >= 85 and experiencia in ('4_6_anos', '6_mais'):
        return 'Sênior'
    elif score_compat >= 70 and experiencia == '2_anos':
        return 'Júnior avançado / Pleno inicial'
    elif score_compat < 50 and experiencia in ('4_6_anos', '6_mais'):
        return f'{base} (evidência fraca)'
    return base

def estimar_area(linguagens: list[str]) -> str:
    areas = {'Backend': {'Python', 'Java', 'Golang', 'Rust', 'Kotlin', 'Ruby', 'C#'}, 'Frontend': {'JavaScript', 'TypeScript'}, 'Mobile': {'Kotlin', 'Swift'}, 'Sistemas': {'C/C++', 'Rust'}, 'Data/ML': {'Python'}}
    contagem: dict[str, int] = {}
    for lang in linguagens:
        for area, langs in areas.items():
            if lang in langs:
                contagem[area] = contagem.get(area, 0) + 1
    if not contagem:
        return 'Não determinado'
    return max(contagem, key=contagem.get)

def experiencia_label(valor: str) -> str:
    mapa = {'6_meses': 'Até 6 meses', '1_ano': '1 ano', '2_anos': '2 anos', '4_6_anos': '4 a 6 anos', '6_mais': '6 ou mais anos'}
    return mapa.get(valor, valor)


# Emoji de cada categoria de projeto (usado em canais e embeds)
EMOJIS_CATEGORIA_PROJETO = {
    'Bots': '🤖', 'SaaS': '☁️', 'Mobile': '📱', 'Web App': '🌐',
    'API / Backend': '⚙️', 'Automação': '🔄', 'Data / ML': '📊',
    'Jogos': '🎮', 'Desktop': '🖥️', 'Outro': '📦',
}


def slug_canal(texto: str, max_len: int = 40) -> str:
    """Converte um texto em slug de canal Discord: minúsculas, sem acentos, hífens."""
    import unicodedata
    texto = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode()
    texto = re.sub(r'[^a-z0-9]+', '-', texto.lower()).strip('-')
    return texto[:max_len].rstrip('-') or 'canal'


def nome_canal(emoji: str, base: str) -> str:
    """Padrão visual de nome de canal do servidor: 'emoji・nome-do-canal'."""
    return f'{emoji}・{slug_canal(base)}'


def nome_canal_projeto(categoria: str, titulo: str) -> str:
    """Nome do canal de vitrine de um projeto: 'emoji-da-categoria・titulo'."""
    emoji = EMOJIS_CATEGORIA_PROJETO.get(categoria, '📦')
    return nome_canal(emoji, titulo[:30])


def parse_valor_brl(texto: str) -> float | None:
    """
    Converte um valor em texto para float, aceitando formatos brasileiros e
    internacionais: '1.500,00', '1500.00', 'R$ 1.500', '1500', '1,500.00'.
    Retorna None se não conseguir interpretar.
    """
    limpo = re.sub(r'(?i)r\$', '', texto).strip().replace(' ', '')
    if not limpo or not re.fullmatch(r'[\d.,]+', limpo):
        return None

    tem_virgula = ',' in limpo
    tem_ponto = '.' in limpo

    if tem_virgula and tem_ponto:
        # O separador decimal é o que aparece por último
        if limpo.rfind(',') > limpo.rfind('.'):
            limpo = limpo.replace('.', '').replace(',', '.')   # 1.500,00
        else:
            limpo = limpo.replace(',', '')                     # 1,500.00
    elif tem_virgula:
        partes = limpo.split(',')
        if len(partes) == 2 and len(partes[1]) <= 2:
            limpo = limpo.replace(',', '.')                    # 1500,00
        else:
            limpo = limpo.replace(',', '')                     # 1,500 (milhar)
    elif tem_ponto:
        partes = limpo.split('.')
        if len(partes) == 2 and len(partes[1]) <= 2:
            pass                                               # 1500.00 — já é decimal
        elif all(len(p) == 3 for p in partes[1:]):
            limpo = limpo.replace('.', '')                     # 1.500 / 1.500.000 (milhar)
        else:
            return None

    try:
        valor = float(limpo)
    except ValueError:
        return None
    return valor if valor >= 0 else None


def formatar_brl(valor: float) -> str:
    """Formata um valor em reais no padrão brasileiro: R$ 1.500,00."""
    inteiro, decimal = f'{valor:,.2f}'.split('.')
    return f"R$ {inteiro.replace(',', '.')},{decimal}"


def formatar_brl_centavos(centavos: int) -> str:
    """Formata um valor em centavos no padrão brasileiro."""
    return formatar_brl(centavos / 100)


def validar_chave_pix(chave: str, tipo: str) -> str | None:
    """
    Valida e normaliza uma chave PIX conforme o tipo.
    Retorna a chave normalizada ou None se inválida.
    """
    chave = chave.strip()
    if tipo == 'CPF':
        digitos = re.sub(r'\D', '', chave)
        return digitos if len(digitos) == 11 else None
    if tipo == 'CNPJ':
        digitos = re.sub(r'\D', '', chave)
        return digitos if len(digitos) == 14 else None
    if tipo == 'EMAIL':
        return chave.lower() if re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', chave) else None
    if tipo == 'PHONE':
        digitos = re.sub(r'\D', '', chave)
        if digitos.startswith('55') and len(digitos) in (12, 13):
            digitos = digitos[2:]
        return digitos if len(digitos) in (10, 11) else None
    if tipo == 'RANDOM':
        limpa = chave.lower()
        return limpa if re.fullmatch(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', limpa) else None
    return None