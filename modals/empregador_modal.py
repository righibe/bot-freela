"""
Modal de formulário para empregadores.
Coleta todos os dados do projeto para validação via API.
"""

import logging
import discord
from discord.ui import Modal, TextInput
from config.settings import (
    COR_PRINCIPAL, COR_SUCESSO, COR_ALERTA, COR_ERRO,
    CARGO_EMPREGADOR_VERIFICADO, CATEGORIA_PROJETOS_ID,
    CATEGORIAS_PROJETO, LINGUAGENS_OPCOES,
)
from services.api_client import validar_empregador_via_api
from embeds.empregador_embed import criar_embed_projeto_aprovado, criar_embed_projeto_reprovado
from embeds.projeto_embed import criar_embed_projeto_listagem
from core.database import (
    Empregador, Projeto, salvar_empregador, salvar_projeto,
    buscar_empregador, _gerar_id,
)
from views.projeto_views import ProjetoInteresseView

logger = logging.getLogger('bot_freeela.modals.empregador')


class EmpregadorModal(Modal, title='Cadastro de Projeto — Empregador'):
    """Modal completo para coleta de dados do empregador e projeto."""

    nome = TextInput(
        label='Seu nome',
        style=discord.TextStyle.short,
        placeholder='Ex: João Silva',
        required=True,
        max_length=100,
    )
    titulo_projeto = TextInput(
        label='Título do projeto',
        style=discord.TextStyle.short,
        placeholder='Ex: Bot de moderação para Discord',
        required=True,
        min_length=5,
        max_length=200,
    )
    descricao_projeto = TextInput(
        label='Descrição detalhada do projeto',
        style=discord.TextStyle.paragraph,
        placeholder='Descreva o projeto: funcionalidades, requisitos, stack...',
        required=True,
        min_length=30,
        max_length=2000,
    )
    valor_projeto = TextInput(
        label='Valor do projeto (R$)',
        style=discord.TextStyle.short,
        placeholder='Ex: 500.00',
        required=True,
        max_length=20,
    )
    experiencia_prazo = TextInput(
        label='Experiência exigida + Prazo (nível | prazo)',
        style=discord.TextStyle.short,
        placeholder='Ex: pleno | 2 semanas',
        required=True,
        max_length=100,
    )

    def __init__(self, user_id: int, thread: discord.Thread, categoria: str):
        super().__init__()
        self.user_id = user_id
        self.thread = thread
        self.categoria = categoria

    async def on_submit(self, interaction: discord.Interaction):
        user = interaction.user
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message('❌ Erro interno.', ephemeral=True)
            return

        # Processar campos
        try:
            valor = float(self.valor_projeto.value.replace('R$', '').replace('.', '').replace(',', '.').strip())
        except ValueError:
            valor = 0.0

        # Parse experiência e prazo
        experiencia = 'qualquer'
        prazo = ''

        exp_prazo_raw = self.experiencia_prazo.value.strip()

        if '|' in exp_prazo_raw:
            parts = exp_prazo_raw.split('|', 1)
            exp_str = parts[0].strip().lower()
            prazo = parts[1].strip()
        else:
            exp_str = exp_prazo_raw.lower()

        # Mapear experiência
        if any(w in exp_str for w in ['junior', 'júnior', 'jr']):
            experiencia = 'junior'
        elif any(w in exp_str for w in ['pleno', 'mid', 'intermediário']):
            experiencia = 'pleno'
        elif any(w in exp_str for w in ['senior', 'sênior', 'sr']):
            experiencia = 'senior'
        else:
            experiencia = 'qualquer'

        # Inferir linguagens baseada em categoria e descrição
        linguagens = self._inferir_stack(self.categoria, self.descricao_projeto.value)

        # Enviar embed de processamento
        embed_proc = discord.Embed(
            title='⏳  Validando seu projeto...',
            description='Estamos analisando a coerência do seu projeto. Aguarde...',
            color=COR_ALERTA,
        )
        await interaction.response.send_message(embed=embed_proc)

        try:
            # ==== MODO DE TESTE ====
            # Se o usuário digitar "TESTE" no título, aprova automaticamente
            if "TESTE" in self.titulo_projeto.value.upper():
                resultado_teste = {
                    'approved': True,
                    'score': 100,
                    'categoria_detectada': self.categoria,
                    'complexidade_estimada': 'baixa',
                    'sugestoes': [],
                    'problemas': []
                }
                await self._aprovar_projeto(
                    guild=guild,
                    user=user,
                    resultado=resultado_teste,
                    linguagens=linguagens,
                    experiencia=experiencia,
                    valor=valor,
                    prazo=prazo,
                )
                await self.thread.send(embed=discord.Embed(title='✅ Modo Teste', description='Projeto aprovado (teste)', color=COR_SUCESSO))
                return
            # =======================

            # Chamar API de validação
            resultado = await validar_empregador_via_api(
                nome=self.nome.value,
                empresa='',
                tipo_projeto=self.categoria,
                titulo=self.titulo_projeto.value,
                descricao=self.descricao_projeto.value,
                linguagens=linguagens,
                experiencia_exigida=experiencia,
                valor=valor,
                prazo=prazo,
            )

            # Validar valor do projeto antes de enviar à API
            if valor < 20 or valor > 50000:
                embed_valor = discord.Embed(
                    title='❌ Valor Inválido',
                    description='O orçamento do projeto deve estar entre **R$ 20,00** e **R$ 50.000,00** para manter o padrão da plataforma.',
                    color=COR_ERRO
                )
                await self.thread.send(embed=embed_valor)
                import asyncio
                await asyncio.sleep(20)
                try:
                    await self.thread.delete()
                except:
                    pass
                return

            if resultado is None:
                # API offline — fazer validação básica local
                resultado = self._validacao_local_fallback(
                    linguagens, valor, self.descricao_projeto.value,
                )

            if resultado.get('approved', False):
                await self._aprovar_projeto(
                    guild=guild,
                    user=user,
                    resultado=resultado,
                    linguagens=linguagens,
                    experiencia=experiencia,
                    valor=valor,
                    prazo=prazo,
                )
            else:
                # Salvar projeto como pendente para aprovação manual
                projeto_pendente = Projeto(
                    id=_gerar_id('proj'),
                    empregador_id=user.id,
                    empregador_nome=self.nome.value,
                    titulo=self.titulo_projeto.value,
                    descricao=self.descricao_projeto.value,
                    categoria=resultado.get('categoria_detectada', self.categoria),
                    linguagens_requeridas=linguagens,
                    experiencia_minima=experiencia,
                    valor=valor,
                    prazo_estimado=prazo,
                    status='pendente',
                )
                salvar_projeto(projeto_pendente)

                dados = {
                    'score': resultado.get('score', 0),
                    'problemas': resultado.get('problemas', []),
                    'sugestoes': resultado.get('sugestoes', []),
                }
                embed = criar_embed_projeto_reprovado(dados)
                await self.thread.send(embed=embed)
                
                # Enviar para log-projetos para aprovação manual
                from config.settings import CANAL_LOG_PROJETOS
                canal_log = guild.get_channel(CANAL_LOG_PROJETOS)
                if canal_log:
                    membro = guild.get_member(user.id)
                    from embeds.review_embed import criar_embed_review_empregador
                    try:
                        embed_review = criar_embed_review_empregador(
                            usuario=membro,
                            nome=self.nome.value,
                            titulo=self.titulo_projeto.value,
                            descricao=self.descricao_projeto.value,
                            score=resultado.get('score', 0),
                            problemas=resultado.get('problemas', [])
                        )
                        embed_review.add_field(name='ID do Projeto', value=f'`{projeto_pendente.id}`', inline=False)
                    except ImportError:
                        # Fallback case
                        embed_review = discord.Embed(title='📋 Revisão Empregador', description=f'**Nome:** {self.nome.value}\n**Projeto:** {self.titulo_projeto.value}\n**ID:** `{projeto_pendente.id}`', color=COR_ALERTA)
                    
                    from views.staff_views import StaffReviewView
                    view = StaffReviewView()
                    await canal_log.send(embed=embed_review, view=view)

                logger.info(
                    'Projeto de %s reprovado | score=%d',
                    user.name, resultado.get('score', 0),
                )
                # Apagar chat após 20 segundos
                import asyncio
                await asyncio.sleep(20)
                try:
                    await self.thread.delete()
                except:
                    pass

        except Exception as e:
            logger.exception('Erro ao validar projeto de %s: %s', user.name, e)
            await self.thread.send(
                embed=discord.Embed(
                    title='❌  Erro na Validação',
                    description='Ocorreu um erro ao validar o projeto. A staff foi notificada.',
                    color=COR_ERRO,
                )
            )

    def _validacao_local_fallback(self, linguagens: list, valor: float, descricao: str) -> dict:
        """Validação local quando a API está offline."""
        problemas = []
        score = 70

        if valor <= 0:
            problemas.append('Valor do projeto não informado ou inválido.')
            score -= 30
        if len(descricao.strip()) < 30:
            problemas.append('Descrição muito curta.')
            score -= 20
        if not linguagens:
            problemas.append('Nenhuma linguagem/tecnologia especificada.')
            score -= 20

        return {
            'approved': len(problemas) == 0,
            'score': max(0, score),
            'problemas': problemas,
            'sugestoes': [],
            'categoria_detectada': self.categoria,
            'complexidade_estimada': 'média',
        }

    async def _aprovar_projeto(
        self,
        guild: discord.Guild,
        user: discord.Member,
        resultado: dict,
        linguagens: list[str],
        experiencia: str,
        valor: float,
        prazo: str,
    ):
        """Processa a aprovação do projeto."""
        # Salvar empregador
        emp = buscar_empregador(user.id)
        if not emp:
            emp = Empregador(
                user_id=user.id,
                username=user.name,
                nome=self.nome.value,
            )
        emp.projetos_criados += 1
        salvar_empregador(emp)

        # Atribuir cargo de empregador
        if CARGO_EMPREGADOR_VERIFICADO:
            cargo = guild.get_role(CARGO_EMPREGADOR_VERIFICADO)
            if cargo:
                try:
                    membro = guild.get_member(user.id)
                    if membro:
                        await membro.add_roles(cargo, reason='Empregador verificado')
                except discord.Forbidden:
                    logger.error('Sem permissão para adicionar cargo empregador a %s', user.name)

        # Criar projeto no banco
        projeto = Projeto(
            id=_gerar_id('proj'),
            empregador_id=user.id,
            empregador_nome=self.nome.value,
            titulo=self.titulo_projeto.value,
            descricao=self.descricao_projeto.value,
            categoria=resultado.get('categoria_detectada', self.categoria),
            linguagens_requeridas=linguagens,
            experiencia_minima=experiencia,
            valor=valor,
            prazo_estimado=prazo,
            status='aberto',
        )
        salvar_projeto(projeto)

        # Enviar embed de aprovação na thread
        dados = {
            'titulo': self.titulo_projeto.value,
            'score': resultado.get('score', 0),
            'categoria': resultado.get('categoria_detectada', self.categoria),
            'complexidade': resultado.get('complexidade_estimada', 'N/A'),
            'sugestoes': resultado.get('sugestoes', []),
        }
        embed = criar_embed_projeto_aprovado(dados)
        await self.thread.send(embed=embed)

        # Publicar como um NOVO CANAL na categoria
        from config.settings import CATEGORIA_PROJETOS_ID
        categoria_projetos = guild.get_channel(CATEGORIA_PROJETOS_ID)
        
        if categoria_projetos and isinstance(categoria_projetos, discord.CategoryChannel):
            import re
            nome_canal = f"{self.categoria[:10].lower()}-{self.titulo_projeto.value[:15].lower().replace(' ', '-')}"
            nome_canal = re.sub(r'[^a-z0-9\-]', '', nome_canal)
            
            try:
                canal_projeto = await guild.create_text_channel(nome_canal, category=categoria_projetos)
                
                from dataclasses import asdict
                embed_listagem = criar_embed_projeto_listagem(asdict(projeto))
                view = ProjetoInteresseView(projeto_id=projeto.id)
                
                # Pings de stack
                pings = []
                from config.settings import CARGOS_LINGUAGEM
                for lang in linguagens:
                    if lang in CARGOS_LINGUAGEM:
                        cargo_lang = guild.get_role(CARGOS_LINGUAGEM[lang])
                        if cargo_lang:
                            pings.append(cargo_lang.mention)
                
                content_msg = ""
                if pings:
                    content_msg = f"{' '.join(pings)} 🚀 Novo projeto postado buscando a stack: **{', '.join(linguagens)}**!"
                else:
                    from config.settings import CARGO_DEV_VERIFICADO
                    if CARGO_DEV_VERIFICADO:
                        cargo_dev = guild.get_role(CARGO_DEV_VERIFICADO)
                        if cargo_dev:
                            content_msg = f"{cargo_dev.mention} 🚀 Novo projeto postado buscando a stack: **{', '.join(linguagens)}**!"
                        
                msg = await canal_projeto.send(content=content_msg, embed=embed_listagem, view=view)
                
                # Salvar message_id para referência futura
                projeto.message_id = msg.id
                salvar_projeto(projeto)
                
                # Disparar DM para os Devs que têm a stack (Mesclagem)
                from core.database import db
                devs = db.get('devs', {})
                for dev_id, dev_data in devs.items():
                    dev_langs = set(dev_data.get('linguagens_confirmadas', []))
                    proj_langs = set(linguagens)
                    match = dev_langs.intersection(proj_langs)
                    if match:
                        membro_dev = guild.get_member(int(dev_id))
                        if membro_dev:
                            try:
                                link_msg = msg.jump_url
                                await membro_dev.send(
                                    f"🚀 **Match de Projeto!**\n\nUm novo projeto que precisa de **{', '.join(match)}** "
                                    f"foi postado!\nCorre no canal {canal_projeto.mention} para clicar em **Tenho Interesse**.\n\n🔗 Link direto: {link_msg}"
                                )
                                logger.info("Notificação DM enviada para o dev %s sobre o projeto %s", membro_dev.name, projeto.id)
                            except Exception:
                                pass
            except discord.Forbidden:
                await self.thread.send('⚠️ O bot não tem permissão para criar canais na categoria de projetos.')
        else:
            await self.thread.send(
                '⚠️ Categoria de projetos não configurada ou não encontrada. '
                'O projeto foi salvo mas não foi publicado automaticamente.'
            )

        logger.info(
            'Projeto "%s" de %s APROVADO e listado | id=%s | valor=%.2f',
            self.titulo_projeto.value, user.name, projeto.id, valor,
        )

    def _inferir_stack(self, categoria: str, descricao: str) -> list[str]:
        """Infere a stack tecnológica baseada na categoria e descrição do projeto."""
        from config.settings import STACK_POR_CATEGORIA, LINGUAGENS_OPCOES

        # Stack base por categoria
        stack_base = STACK_POR_CATEGORIA.get(categoria, [])

        # Detectar tecnologias mencionadas na descrição
        texto = descricao.lower()
        tecnologias_detectadas = []
        for lang in LINGUAGENS_OPCOES:
            if lang.lower() in texto:
                tecnologias_detectadas.append(lang)

        # Combinar: base + detectadas, sem duplicatas
        stack_inferida = list(set(stack_base + tecnologias_detectadas))

        # Se nenhuma detectada, usar pelo menos 2 da base
        if not stack_inferida and stack_base:
            stack_inferida = stack_base[:2]

        return stack_inferida

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.exception('Erro no modal de empregador: %s', error)
        try:
            await interaction.response.send_message(
                '❌ Ocorreu um erro ao processar o formulário.',
                ephemeral=True,
            )
        except discord.InteractionResponded:
            await interaction.followup.send(
                '❌ Ocorreu um erro ao processar o formulário.',
                ephemeral=True,
            )
