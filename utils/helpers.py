import re
import logging
from datetime import datetime, timezone
logger = logging.getLogger('bot_freeela.utils')

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