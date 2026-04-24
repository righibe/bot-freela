import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field
import aiohttp
from config.settings import LINGUAGENS_ALIASES
logger = logging.getLogger('bot_freeela.services.github')
GITHUB_API_BASE = 'https://api.github.com'

@dataclass
class GitHubProfile:
    existe: bool = False
    username: str = ''
    nome: str = ''
    bio: str = ''
    repos_publicos: int = 0
    seguidores: int = 0
    seguindo: int = 0
    criado_em: datetime | None = None
    atualizado_em: datetime | None = None
    linguagens_detectadas: list[str] = field(default_factory=list)
    repos_recentes: int = 0
    idade_conta_anos: float = 0.0
    erro: str | None = None

async def buscar_perfil_github(username: str) -> GitHubProfile:
    profile = GitHubProfile(username=username)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f'{GITHUB_API_BASE}/users/{username}', headers={'Accept': 'application/vnd.github.v3+json'}, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 404:
                    profile.existe = False
                    profile.erro = 'Perfil não encontrado'
                    return profile
                elif resp.status != 200:
                    profile.erro = f'Erro na API do GitHub: {resp.status}'
                    return profile
                data = await resp.json()
            profile.existe = True
            profile.nome = data.get('name') or ''
            profile.bio = data.get('bio') or ''
            profile.repos_publicos = data.get('public_repos', 0)
            profile.seguidores = data.get('followers', 0)
            profile.seguindo = data.get('following', 0)
            criado_str = data.get('created_at')
            if criado_str:
                profile.criado_em = datetime.fromisoformat(criado_str.replace('Z', '+00:00'))
                delta = datetime.now(timezone.utc) - profile.criado_em
                profile.idade_conta_anos = round(delta.days / 365.25, 1)
            atualizado_str = data.get('updated_at')
            if atualizado_str:
                profile.atualizado_em = datetime.fromisoformat(atualizado_str.replace('Z', '+00:00'))
            async with session.get(f'{GITHUB_API_BASE}/users/{username}/repos', params={'per_page': 100, 'sort': 'pushed', 'direction': 'desc'}, headers={'Accept': 'application/vnd.github.v3+json'}, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    repos = await resp.json()
                else:
                    repos = []
            linguagens_set: set[str] = set()
            agora = datetime.now(timezone.utc)
            for repo in repos:
                lang = repo.get('language')
                if lang:
                    lang_lower = lang.lower()
                    nome_interno = LINGUAGENS_ALIASES.get(lang_lower)
                    if nome_interno:
                        linguagens_set.add(nome_interno)
                pushed_at_str = repo.get('pushed_at')
                if pushed_at_str:
                    pushed_at = datetime.fromisoformat(pushed_at_str.replace('Z', '+00:00'))
                    if (agora - pushed_at).days <= 180:
                        profile.repos_recentes += 1
            for repo in repos[:15]:
                repo_name = repo.get('full_name', '')
                if not repo_name:
                    continue
                try:
                    async with session.get(f'{GITHUB_API_BASE}/repos/{repo_name}/languages', headers={'Accept': 'application/vnd.github.v3+json'}, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status == 200:
                            langs_data = await resp.json()
                            for lang_name in langs_data:
                                lang_lower = lang_name.lower()
                                nome_interno = LINGUAGENS_ALIASES.get(lang_lower)
                                if nome_interno:
                                    linguagens_set.add(nome_interno)
                except Exception:
                    continue
            profile.linguagens_detectadas = sorted(linguagens_set)
    except aiohttp.ClientError as e:
        profile.erro = f'Erro de conexão: {e}'
        logger.error('Erro ao buscar GitHub para %s: %s', username, e)
    except Exception as e:
        profile.erro = f'Erro inesperado: {e}'
        logger.exception('Erro inesperado ao buscar GitHub para %s', username)
    return profile