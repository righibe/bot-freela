import logging
from dataclasses import dataclass
import aiohttp
logger = logging.getLogger('bot_freeela.services.linkedin')

@dataclass
class LinkedInProfile:
    existe: bool = False
    url_valida: bool = False
    username: str = ''
    erro: str | None = None

async def verificar_linkedin(username: str) -> LinkedInProfile:
    profile = LinkedInProfile(username=username)
    url = f'https://www.linkedin.com/in/{username}'
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}, timeout=aiohttp.ClientTimeout(total=15), allow_redirects=True) as resp:
                if resp.status == 200:
                    profile.existe = True
                    profile.url_valida = True
                elif resp.status in (301, 302):
                    final_url = str(resp.url)
                    if '/in/' in final_url:
                        profile.existe = True
                        profile.url_valida = True
                    else:
                        profile.existe = False
                        profile.url_valida = False
                else:
                    profile.existe = False
                    profile.url_valida = False
    except aiohttp.ClientError as e:
        profile.erro = f'Erro de conexão: {e}'
        logger.error('Erro ao verificar LinkedIn para %s: %s', username, e)
    except Exception as e:
        profile.erro = f'Erro inesperado: {e}'
        logger.exception('Erro inesperado ao verificar LinkedIn para %s', username)
    return profile