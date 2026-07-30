# 🥑 Bot Freeela

Plataforma completa de **freelancing dentro do Discord**: verificação de desenvolvedores, publicação de projetos, matching, negociação e **pagamento automático via PIX** (AbacatePay) com repasse instantâneo ao dev.

## Como funciona

```
Dev se verifica ──► GitHub/LinkedIn analisados ──► cargo + stack confirmada
                                                        │
Empregador cria projeto ──► validação automática ──► vitrine de projetos
                                                        │
Dev clica "Tenho Interesse" ──► canal de negociação ──► ambos fecham parceria
                                                        │
Canal privado do projeto (texto + voz) ──► trabalho entregue
                                                        │
Empregador clica "✅ Concluir & Pagar" ──► QR Code PIX no canal
                                                        │
Pagamento confirmado ──► 85% enviado ao dev via PIX ──► 15% fica na plataforma
                                                        │
Recibos no canal + DM ──► projeto concluído e arquivado automaticamente
```

## 💳 Pagamentos (AbacatePay)

- O **dev cadastra a chave PIX** com `/configurar_pagamento` (ou pelo botão que o bot envia no canal do projeto). Tipos aceitos: CPF, CNPJ, e-mail, telefone e chave aleatória — com validação de formato.
- Ao concluir, o bot gera um **QR Code PIX** (imagem + copia-e-cola) no valor fechado do projeto.
- A confirmação é automática: **polling** a cada 20s + **webhook** (`POST /webhooks/abacatepay`) para confirmação em tempo real.
- Confirmado o pagamento, o bot **envia o repasse na hora** (`85%`) para a chave PIX do dev e retém a **taxa de 15%** na conta AbacatePay da plataforma.
- Com uma **chave de API de desenvolvimento**, o botão "🧪 Simular Pagamento" permite testar todo o fluxo sem dinheiro real.
- Se um repasse falhar, a staff é alertada no canal de logs com o valor e a chave para processamento manual (`/receita_plataforma` lista as pendências).

## 🚀 Instalação

```bash
# 1. Clonar e entrar no projeto
git clone <repo> && cd bot_freeela

# 2. Criar o ambiente virtual
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Linux/Mac

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Configurar
copy .env.example .env       # e preencha DISCORD_TOKEN e ABACATEPAY_API_KEY

# 5. Rodar
python app.py
```

Na primeira execução o bot cria automaticamente os cargos, categorias e canais no servidor (setup automático) e migra dados antigos em JSON para o banco SQLite (`data/freeela.db`).

## 🗄️ Banco de dados

SQLite (arquivo único `data/freeela.db`, modo WAL). Tabelas: `devs`, `empregadores`, `projetos`, `candidaturas`, `projetos_ativos`, `pagamentos`, `cooldowns`. As transições de status de pagamento são atômicas — o repasse nunca é enviado duas vezes, mesmo com webhook e polling simultâneos.

## 🤖 Comandos

| Comando | Quem usa | Descrição |
|---|---|---|
| `/meu_perfil` | Dev | Perfil verificado + chave PIX cadastrada |
| `/configurar_pagamento` | Dev | Cadastrar/atualizar chave PIX |
| `/meus_projetos` | Dev | Projetos ativos |
| `/compatibilidade` | Dev | Compatibilidade com um projeto |
| `/listar_projetos` | Todos | Projetos abertos |
| `/termos` | Todos | Termos de Uso + botão de aceite |
| `/aceites_termos` | Staff | Estatísticas de aceite dos Termos |
| `/tickets` | Staff | Estatísticas dos tickets de suporte |
| `/status_plataforma` | Staff | Métricas gerais + receita |
| `/receita_plataforma` | Staff | Receita da taxa de 15% + repasses com erro |
| `/status_verificacao` | Staff | Diagnóstico de canais/cargos/permissões |
| `/setup_verificacao` `/setup_empregador` `/setup_atualizar_perfil` | Staff | Reenviar embeds iniciais |

## 📁 Estrutura

```
bot_freeela/
├── app.py                    # Entry point: bot + API FastAPI
├── config/settings.py        # IDs, constantes, config de pagamento
├── core/
│   ├── database.py           # SQLite (devs, projetos, pagamentos...)
│   ├── matching_engine.py    # Compatibilidade dev ↔ projeto
│   ├── protection.py         # Anti-spam, cooldowns, limites
│   └── setup_manager.py      # Setup automático do servidor
├── services/
│   ├── abacatepay_service.py # Cobrança PIX, status, repasse (split 85/15)
│   ├── github_service.py     # Análise de perfil GitHub
│   └── ...
├── cogs/
│   ├── pagamentos.py         # Orquestração do pagamento completo
│   ├── execucao.py           # Ambiente do projeto, conclusão, limpeza
│   └── ...
├── views/                    # Botões, selects e fluxos interativos
├── modals/                   # Formulários
├── embeds/                   # Mensagens visuais
└── api/                      # FastAPI: validação + webhook AbacatePay
```

## 📜 Termos de Uso

O documento completo está em [`TERMOS_DE_USO.md`](TERMOS_DE_USO.md) (contrato de adesão: natureza de intermediação, taxa de 15%, mandato de recebimento, LGPD, limitação de responsabilidade, proibição de pagamento por fora, foro).

- O **aceite é obrigatório** antes de: verificar-se como dev, publicar projeto, candidatar-se e fechar parceria.
- Cada aceite é registrado no banco (`aceites_termos`) com **usuário, versão, contexto e data/hora UTC** — a prova do aceite eletrônico.
- Ao editar o documento, **incremente `TERMOS_VERSAO`** em `config/settings.py`: todos os usuários precisarão aceitar a nova versão.
- Comandos: `/termos` (qualquer usuário) e `/aceites_termos` (staff).
- O setup automático cria o canal `#termos-de-uso` com o resumo, o documento anexo e o botão de aceite.

## 🔒 Segurança

- Webhook validado por **secret na URL** + **assinatura HMAC-SHA256**.
- Chaves PIX validadas por formato e exibidas sempre **mascaradas**.
- Transições de pagamento atômicas no banco (proteção contra repasse duplo).
- Cooldowns e limites diários contra spam de candidaturas/verificações.
