import logging
import discord
from discord.ui import View, Select
from config.settings import OPCOES_EXPERIENCIA, COR_PRINCIPAL, COR_ERRO, MSG_REPROVADO_EXPERIENCIA, MSG_REPROVADO_AUTO, MSG_REVIEW, COR_ALERTA, COR_SUCESSO, CARGO_DEV_VERIFICADO
from utils.helpers import enviar_msg_erro_api
from embeds.verificacao_embed import criar_embed_resultado_dev, criar_embed_aprovado
from embeds.review_embed import criar_embed_review
from services.api_client import validar_dev_via_api

logger = logging.getLogger('bot_freeela.views.selecao_experiencia')

class SelecaoExperienciaView(View):
    def __init__(self, user_id: int, github: str, linkedin: str, descricao: str, thread: discord.Thread, linguagens: list[str]):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.github = github
        self.linkedin = linkedin
        self.descricao = descricao
        self.thread = thread
        self.linguagens = linguagens
        
        opcoes = [discord.SelectOption(label=label, value=valor, emoji=_emoji_experiencia(valor)) for label, valor in OPCOES_EXPERIENCIA]
        select = Select(placeholder='Selecione seu tempo de experiência...', min_values=1, max_values=1, options=opcoes, custom_id='select_experiencia')
        select.callback = self.callback_experiencia
        self.add_item(select)

    async def callback_experiencia(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message('❌ Apenas o usuário em verificação pode interagir.', ephemeral=True)
            return

        # Verificar se já tem o cargo de dev verificado
        from config.settings import get_cargo_dev_verificado
        cargo_dev = get_cargo_dev_verificado(interaction.guild)
        if cargo_dev and cargo_dev in interaction.user.roles:
            for child in self.children:
                child.disabled = True
            try:
                await interaction.message.edit(view=self)
            except Exception:
                pass
            await interaction.response.send_message('✅ Você já é um desenvolvedor verificado.', ephemeral=True)
            return
            
        experiencia = interaction.data['values'][0]
        
        # Desabilitar seleções para que o usuário não clique de novo
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        
        # Bloquear experiência < 1 ano no Discord
        if experiencia in ('6_meses',):
            embed = discord.Embed(
                title='❌ Experiência Insuficiente',
                description='Você precisa ter **no mínimo 1 ano de experiência** para se verificar como desenvolvedor.',
                color=COR_ERRO
            )
            embed.set_footer(text='Você pode tentar novamente quando tiver 1 ano de experiência.')
            await self.thread.send(embed=embed)
            await _apagar_thread(self.thread, delay=5)
            logger.info('Usuário %s reprovado por experiência insuficiente', interaction.user.name)
            return
            
        await interaction.followup.send('🔄 Processando sua verificação na API... Isso pode levar alguns segundos.', ephemeral=True)
        
        user = interaction.user
        guild = interaction.guild
        github_url = self.github.strip()
        linkedin_url = self.linkedin.strip() if self.linkedin else ''
        descricao_txt = self.descricao.strip()

        logger.info('=== INICIANDO SUBMIT VERIFICAÇÃO DEV ===')
        logger.info('Usuário: %s (%s)', user.name, user.id)
        logger.info('GitHub: %s', github_url)
        logger.info('LinkedIn: %s', linkedin_url)
        logger.info('Experiência: %s', experiencia)
        logger.info('Linguagens: %s', self.linguagens)
        logger.info('Descrição: %s', descricao_txt[:100] + '...' if len(descricao_txt) > 100 else descricao_txt)

        # SIMULAÇÃO LOCAL (FORÇADA) SE FOR "TESTE"
        if github_url.upper() == "TESTE":
            from services.scoring_service import ResultadoScore
            resultado = ResultadoScore(
                compatibilidade=100, integridade=100, score_final=100,
                aprovado=True, requires_review=False,
                linguagens_selecionadas=self.linguagens,
                linguagens_detectadas=self.linguagens,
                linguagens_confirmadas=self.linguagens,
                senioridade=experiencia,
                motivos_reprovacao=[], penalizacoes=[], detalhes_compat=[]
            )
            await self._aprovar_dev(guild, user, resultado, github_url, linkedin_url, experiencia)
            return

        resultado_api = await validar_dev_via_api(
            github=github_url,
            linkedin=linkedin_url,
            descricao=descricao_txt,
            linguagens=self.linguagens,
            experiencia=experiencia
        )
        if not resultado_api:
            await enviar_msg_erro_api(self.thread, user)
            return
            
        from services.scoring_service import ResultadoScore
        resultado = ResultadoScore(
            compatibilidade=resultado_api.get('compatibility', 0),
            integridade=resultado_api.get('integrity', 50),
            score_final=resultado_api.get('compatibility', 0),
            aprovado=resultado_api.get('approved', False),
            requires_review=resultado_api.get('needs_review', False),
            linguagens_selecionadas=self.linguagens,
            linguagens_detectadas=resultado_api.get('detected_languages', []),
            linguagens_confirmadas=resultado_api.get('validated_languages', []),
            senioridade=experiencia,
            motivos_reprovacao=resultado_api.get('rejection_reasons', []),
            penalizacoes=[],
            detalhes_compat=[]
        )

        if resultado.aprovado:
            logger.info('✅ RESULTADO APROVADO - Chamando _aprovar_dev')
            await self._aprovar_dev(guild, user, resultado, github_url, linkedin_url, experiencia)
        elif resultado.requires_review:
            logger.info('⚠️ RESULTADO REQUIRES REVIEW - Chamando _enviar_review')
            await self._enviar_review(guild, user, resultado, github_url, linkedin_url, experiencia)
        else:
            logger.info('❌ RESULTADO REPROVADO - Chamando _reprovar_dev')
            await self._reprovar_dev(user, resultado)

    def _get_cargo_dev(self, guild: discord.Guild) -> discord.Role | None:
        from config.settings import get_cargo_dev_verificado, DEV_ROLE_NAME, CARGO_DEV_VERIFICADO

        cargo = get_cargo_dev_verificado(guild)
        if cargo:
            logger.info('Cargo Dev Verificado encontrado: %s (ID: %s)', cargo.name, cargo.id)
            return cargo

        logger.error('Cargo "%s" não encontrado no servidor %s via nome ou ID %s', DEV_ROLE_NAME, guild.name, CARGO_DEV_VERIFICADO)
        logger.info('Cargos disponíveis no servidor %s:', guild.name)
        for role in guild.roles[:20]:
            logger.info('  - %s (ID: %s)', role.name, role.id)
        return None

    async def _aprovar_dev(self, guild: discord.Guild, user: discord.Member, resultado, github_url: str, linkedin_url: str, experiencia: str):
        logger.info('=== INICIANDO APROVAÇÃO DEV ===')
        logger.info('Usuário: %s (%s)', user.name, user.id)
        logger.info('Guild: %s (%s)', guild.name, guild.id)
        logger.info('Resultado aprovado: %s', resultado.aprovado)
        logger.info('Linguagens confirmadas: %s', resultado.linguagens_confirmadas)
        logger.info('Experiência: %s', experiencia)

        from config.settings import CARGOS_LINGUAGEM, CARGOS_EXPERIENCIA
        from core.database import DevVerificado, salvar_dev
        
        # Cargo geral
        cargo = self._get_cargo_dev(guild)
        cargo_assigned = False
        if cargo:
            bot_member = guild.me
            bot_role_name = bot_member.top_role.name if bot_member else 'UNKNOWN'
            bot_role_position = bot_member.top_role.position if bot_member else -1
            logger.info('Tentando atribuir cargo: %s (%s) ao usuário %s (%s)', cargo.name, cargo.id, user.name, user.id)
            logger.info('Bot top role: %s (posição %s)', bot_role_name, bot_role_position)
            logger.info('Cargo alvo posição: %s', cargo.position)

            # Verificar se o bot tem permissão para gerenciar roles
            if not bot_member:
                logger.error('Não foi possível determinar o membro do bot no servidor %s', guild.name)
            elif not bot_member.guild_permissions.manage_roles:
                logger.error('Bot não tem permissão para gerenciar roles no servidor %s', guild.name)
            elif cargo.position >= bot_member.top_role.position:
                logger.error('Cargo %s está acima do cargo mais alto do bot (%s)', cargo.name, bot_member.top_role.name)
            else:
                try:
                    await user.add_roles(cargo, reason='Aprovado na verificação Dev')
                    cargo_assigned = True
                    logger.info('✅ Cargo %s atribuído com sucesso ao usuário %s', cargo.name, user.name)
                except discord.Forbidden:
                    logger.error('❌ Sem permissão para adicionar cargo %s ao usuário %s', cargo.id, user.id)
                except Exception as e:
                    logger.error('❌ Erro ao atribuir cargo Dev Verificado a %s: %s', user.id, e)
        else:
            logger.error('❌ Cargo de Dev Verificado não encontrado')

        if not cargo_assigned:
            await self.thread.send(
                '⚠️ Não foi possível atribuir o cargo **Desenvolvedor Verificado**. Verifique se eu tenho permissão **Manage Roles** e se meu cargo está acima de **Desenvolvedor Verificado** na hierarquia.'
            )

        # Cargos específicos das linguagens
        for lang in resultado.linguagens_confirmadas:
            if lang in CARGOS_LINGUAGEM:
                cargo_id = CARGOS_LINGUAGEM[lang]
                cargo_lang = guild.get_role(cargo_id)
                if cargo_lang:
                    try:
                        await user.add_roles(cargo_lang, reason=f'Stack confirmada: {lang}')
                    except discord.Forbidden:
                        pass
        
        # Cargo de experiência
        if experiencia in CARGOS_EXPERIENCIA:
            cargo_exp_id = CARGOS_EXPERIENCIA[experiencia]
            cargo_exp = guild.get_role(cargo_exp_id)
            if cargo_exp:
                try:
                    await user.add_roles(cargo_exp, reason=f'Experiência: {experiencia}')
                except discord.Forbidden:
                    logger.error('Sem permissão para adicionar cargo de experiência %s', cargo_exp_id)
        
        embed_thread = criar_embed_resultado_dev(resultado)
        await self.thread.send(embed=embed_thread)
        
        embed_aprovado = criar_embed_aprovado(user)
        embed_aprovado.add_field(name='Suas Linguagens', value=', '.join(resultado.linguagens_confirmadas), inline=False)
        embed_aprovado.add_field(name='Experiência', value=experiencia.replace('_', ' ').title(), inline=True)
        await self.thread.send(content=f'||{user.mention}||', embed=embed_aprovado)
        
        # Envia também um log (se quiser manter um histórico)
        from config.settings import CANAL_LOG_DEV
        canal_log = guild.get_channel(CANAL_LOG_DEV)
        if canal_log:
            try:
                await canal_log.send(embed=embed_aprovado)
            except:
                pass
                
        # Salvar dev verificado no banco local para permitir candidaturas e matching
        dev_salvo = DevVerificado(
            user_id=user.id,
            username=user.name,
            linguagens_confirmadas=resultado.linguagens_confirmadas,
            experiencia=experiencia,
            senioridade=resultado.senioridade,
            area=resultado.area_principal,
            github_url=github_url,
            linkedin_url=linkedin_url,
            compatibilidade=resultado.compatibilidade,
            integridade=resultado.integridade,
            data_verificacao='',
            projetos_ativos=0,
        )
        salvar_dev(dev_salvo)
        logger.info('Usuário %s (%s) APROVADO automaticamente', user.name, user.id)
        await _apagar_thread(self.thread, delay=5)

    async def _reprovar_dev(self, user: discord.Member, resultado):
        embed = discord.Embed(title='❌  Verificação Reprovada', description=MSG_REPROVADO_AUTO, color=COR_ERRO)
        motivos = '\n'.join((f'• {m}' for m in resultado.motivos_reprovacao))
        embed.add_field(name='Motivos', value=motivos)
        embed.set_footer(text='Você pode tentar novamente em 30 dias. Este chat será apagado em 20 segundos.')
        await self.thread.send(embed=embed)
        logger.info('Usuário %s (%s) REPROVADO automaticamente', user.name, user.id)
        await _apagar_thread(self.thread, delay=5)

    async def _enviar_review(self, guild: discord.Guild, user: discord.Member, resultado, github_url: str, linkedin_url: str, experiencia: str):
        embed_thread = discord.Embed(title='📋  Enviado para Revisão', description=MSG_REVIEW, color=COR_ALERTA)
        embed_thread.add_field(name='📈  Compatibilidade', value=f'**{resultado.compatibilidade}%**', inline=True)
        embed_thread.add_field(name='🔒  Integridade', value=f'**{resultado.integridade}%**', inline=True)
        if resultado.motivos_reprovacao:
            embed_thread.add_field(name='📌  Motivos', value='\n'.join((f'• {m}' for m in resultado.motivos_reprovacao)), inline=False)
        embed_thread.set_footer(text='Esta thread será arquivada em breve.')
        await self.thread.send(embed=embed_thread)
        
        from config.settings import CANAL_LOG_DEV
        from views.staff_views import StaffReviewView
        
        canal_review = guild.get_channel(CANAL_LOG_DEV)
        if canal_review:
            membro = guild.get_member(user.id)
            if membro:
                from modals.perfil_profissional import logger # fallback
                def exp_label(val):
                    for lbl, v in OPCOES_EXPERIENCIA:
                        if v == val: return lbl
                    return val
                    
                embed_review = criar_embed_review(usuario=membro, resultado=resultado, github_url=github_url, linkedin_url=linkedin_url, descricao=self.descricao, experiencia_label=exp_label(experiencia))
                view = StaffReviewView()
                await canal_review.send(embed=embed_review, view=view)
        logger.info('Usuário %s (%s) enviado para REVIEW no log-dev', user.name, user.id)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

async def _arquivar_thread(channel):
    import asyncio
    await asyncio.sleep(10)
    try:
        if isinstance(channel, discord.Thread):
            await channel.edit(archived=True, locked=True)
    except Exception as e:
        logger.error('Erro ao arquivar thread: %s', e)

async def _apagar_thread(channel, delay: int = 5):
    import asyncio
    await asyncio.sleep(delay)
    try:
        if isinstance(channel, discord.Thread) or isinstance(channel, discord.TextChannel):
            await channel.delete(reason='Verificação concluída')
            return
    except Exception as e:
        logger.error('Erro ao apagar thread: %s', e)
    try:
        if isinstance(channel, discord.Thread):
            await channel.edit(archived=True, locked=True, reason='Falha ao apagar thread')
    except Exception as e:
        logger.error('Erro ao arquivar thread como fallback: %s', e)

def _emoji_experiencia(valor: str) -> str:
    emojis = {'6_meses': '🌱', '1_ano': '📗', '2_anos': '📘', '4_6_anos': '📙', '6_mais': '📕'}
    return emojis.get(valor, '📖')