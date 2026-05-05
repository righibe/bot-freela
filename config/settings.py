"""
Configurações centrais do sistema Freeela.
Contém IDs de canais, cargos, constantes de validação e mensagens.
"""

# ══════════════════════════════════════════════════════
#  CANAIS
# ══════════════════════════════════════════════════════
CANAL_VERIFICAR_DEV = 1495614476060459040
CANAL_VERIFICAR_EMPREGADOR = 1495616185767559360          # Atualizar com o ID real
CATEGORIA_PROJETOS_ID = 1500684318412898427               # Atualizar com o ID real
CATEGORIA_NEGOCIACAO_ID = 1500684319646027858                               # Atualizar com o ID real
CANAL_LOG_DEV = 1497289159344128081                       # Atualizar com o ID real
CANAL_LOG_PROJETOS = 1500684578291978240                  # Atualizar com o ID real

# ══════════════════════════════════════════════════════
#  CARGOS
# ══════════════════════════════════════════════════════
CARGO_DEV_VERIFICADO = 1500684314999001108
CARGO_EMPREGADOR_VERIFICADO = 1500684315896320012         # Atualizar com o ID real
CARGO_STAFF = 1500684317305868451                         # Atualizar com o ID real

CARGOS_LINGUAGEM = {
    'Java': 1495848927008915801,
    'Python': 1495848994482688121,
    'Rust': 1495849031807799348,
    'JavaScript': 1495849187634577428,
    'Golang': 1495849319910080623,
    'Kotlin': 1495849408762220795,
    'C/C++': 1495849467335938211,
    'Swift': 1495849566140891256,
    'Ruby': 1495849647028179105,
}

# ══════════════════════════════════════════════════════
#  LINGUAGENS
# ══════════════════════════════════════════════════════
LINGUAGENS_OPCOES = [
    'Python', 'Java', 'Rust', 'JavaScript', 'TypeScript',
    'Golang', 'Kotlin', 'C/C++', 'C#', 'Swift', 'Ruby',
]

LINGUAGENS_ALIASES = {
    'python': 'Python', 'java': 'Java', 'rust': 'Rust',
    'javascript': 'JavaScript', 'typescript': 'TypeScript',
    'go': 'Golang', 'golang': 'Golang', 'kotlin': 'Kotlin',
    'c': 'C/C++', 'c++': 'C/C++', 'cpp': 'C/C++',
    'c#': 'C#', 'csharp': 'C#', 'swift': 'Swift', 'ruby': 'Ruby',
}

OPCOES_EXPERIENCIA = [
    ('Até 6 meses', '6_meses'),
    ('1 ano', '1_ano'),
    ('2 anos', '2_anos'),
    ('4 a 6 anos', '4_6_anos'),
    ('6 ou mais anos', '6_mais'),
]

# ══════════════════════════════════════════════════════
#  CATEGORIAS DE PROJETO
# ══════════════════════════════════════════════════════
CATEGORIAS_PROJETO = [
    'Bots', 'SaaS', 'Mobile', 'Web App', 'API / Backend',
    'Automação', 'Data / ML', 'Jogos', 'Desktop', 'Outro',
]

PALAVRAS_CHAVE_CATEGORIA = {
    'Bots': ['bot', 'discord', 'telegram', 'whatsapp', 'chatbot', 'automação de chat', 'slash command'],
    'SaaS': ['saas', 'plataforma', 'dashboard', 'painel', 'assinatura', 'multi-tenant', 'subscription'],
    'Mobile': ['mobile', 'android', 'ios', 'flutter', 'react native', 'app móvel', 'aplicativo'],
    'Web App': ['web', 'site', 'frontend', 'landing page', 'ecommerce', 'loja virtual', 'portal'],
    'API / Backend': ['api', 'backend', 'rest', 'graphql', 'microserviço', 'servidor', 'endpoint'],
    'Automação': ['automação', 'scraping', 'crawler', 'pipeline', 'cron', 'agendamento', 'etl'],
    'Data / ML': ['data', 'machine learning', 'ia', 'inteligência artificial', 'dados', 'modelo', 'treinamento', 'dataset'],
    'Jogos': ['jogo', 'game', 'unity', 'godot', 'pygame', 'unreal'],
    'Desktop': ['desktop', 'electron', 'tauri', 'gui', 'interface gráfica', 'tkinter', 'qt'],
    'Outro': [],
}

STACK_POR_CATEGORIA = {
    'Bots': ['Python', 'JavaScript', 'TypeScript', 'Java', 'Node.js'],
    'SaaS': ['Python', 'JavaScript', 'TypeScript', 'Java', 'C#', 'Ruby', 'Golang', 'Rust'],
    'Mobile': ['Kotlin', 'Swift', 'JavaScript', 'TypeScript', 'React Native', 'Dart'],
    'Web App': ['JavaScript', 'TypeScript', 'React', 'Vue', 'Angular', 'Python', 'Ruby', 'Java', 'C#'],
    'API / Backend': ['Python', 'Java', 'Node.js', 'Golang', 'Rust', 'C#'],
    'Automação': ['Python', 'JavaScript', 'Bash', 'Golang'],
    'Data / ML': ['Python', 'R', 'Julia'],
    'Jogos': ['C#', 'C/C++', 'Python', 'Java'],
    'Desktop': ['Python', 'JavaScript', 'C#', 'Java', 'Rust'],
    'Outro': ['Python', 'JavaScript'],
}

EXPERIENCIA_PROJETO_OPCOES = [
    ('Júnior (até 1 ano)', 'junior'),
    ('Pleno (1-4 anos)', 'pleno'),
    ('Sênior (4+ anos)', 'senior'),
    ('Qualquer nível', 'qualquer'),
]

# ══════════════════════════════════════════════════════
#  SCORES E LIMITES
# ══════════════════════════════════════════════════════
SCORE_COMPATIBILIDADE_MIN = 65
SCORE_INTEGRIDADE_MIN = 70
LINGUAGENS_CONFIRMADAS_MIN = 2

# Empregador
SCORE_EMPREGADOR_MIN = 60
VALOR_MINIMO_PROJETO = 50.0     # R$
VALOR_MAXIMO_PROJETO = 500000.0  # R$
DESCRICAO_MINIMA_PROJETO = 30   # caracteres

# Proteção
MAX_PROJETOS_ATIVOS_POR_DEV = 3
COOLDOWN_CANDIDATURA_SEGUNDOS = 300     # 5 minutos
COOLDOWN_VERIFICACAO_SEGUNDOS = 3600    # 1 hora
MAX_CANDIDATURAS_DIA = 10
DESCRICAO_MINIMA_INTERESSE = 10

# ══════════════════════════════════════════════════════
#  CORES
# ══════════════════════════════════════════════════════
COR_PRINCIPAL = 5793266
COR_SUCESSO = 5763719
COR_ALERTA = 16705372
COR_ERRO = 15548997
COR_DIAGNOSTICO = 2829617
COR_REVIEW = 15418782
COR_PROJETO = 3447003
COR_MATCHING = 16750899
COR_EXECUCAO = 1752220

# ══════════════════════════════════════════════════════
#  MENSAGENS
# ══════════════════════════════════════════════════════
MSG_REPROVADO_EXPERIENCIA = 'A verificação dev é destinada para membros com pelo menos **1 ano de experiência prática** em programação.'
MSG_VERIFICACAO_INICIADA = 'Sua verificação foi iniciada! Siga as etapas abaixo para completar o processo.'
MSG_PROCESSANDO = '⏳ Estamos analisando seus dados… Isso pode levar alguns segundos.'
MSG_APROVADO = '🎉 **Parabéns!** Você foi aprovado como **Desenvolvedor Verificado**!\nSeus cargos foram atribuídos automaticamente.'
MSG_REVIEW = '📋 Sua verificação foi encaminhada para **revisão manual** pela staff.\nVocê será notificado quando houver uma resposta.'
MSG_ERRO_API = '❌ Ocorreu um erro ao se comunicar com nossos servidores. Tente novamente mais tarde.'
MSG_REPROVADO_AUTO = 'Infelizmente seu perfil não atingiu os requisitos mínimos neste momento.'
MSG_APROVADO_AUTO = '🎉 Parabéns! Sua verificação foi aprovada automaticamente!'

# API
API_BASE_URL = 'http://127.0.0.1:8000'
API_HOST = '127.0.0.1'
API_PORT = 8000