import logging
import discord
from discord.ui import View, Select
from config.settings import OPCOES_EXPERIENCIA, COR_PRINCIPAL, COR_ERRO, MSG_REPROVADO_EXPERIENCIA, MSG_REPROVADO_AUTO, MSG_REVIEW, COR_ALERTA, COR_SUCESSO
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
            await _arquivar_thread(self.thread)
            logger.info('Usuário %s reprovado por experiência insuficiente', interaction.user.name)
            return
            
        await interaction.followup.send('🔄 Processando sua verificação na API... Isso pode levar alguns segundos.', ephemeral=True)
        
        user = interaction.user
        guild = interaction.guild
        
        github_url = self.github.strip()
        linkedin_url = self.linkedin.strip() if self.linkedin else ''
        descricao_txt = self.descricao.strip()

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
            await self._aprovar_dev(guild, user, resultado, github_url, linkedin_url)
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
            await self._aprovar_dev(guild, user, resultado, github_url, linkedin_url, experiencia)
        elif resultado.requires_review:
            await self._enviar_review(guild, user, resultado, github_url, linkedin_url, experiencia)
        else:
            await self._reprovar_dev(user, resultado)

    async def _aprovar_dev(self, guild: discord.Guild, user: discord.Member, resultado, github_url: str, linkedin_url: str, experiencia: str):
        from config.settings import CARGO_DEV_VERIFICADO, CARGOS_LINGUAGEM
        from core.database import DevVerificado, salvar_dev
        
        # Cargo geral
        cargo = guild.get_role(CARGO_DEV_VERIFICADO)
        if cargo:
            try:
                await user.add_roles(cargo, reason='Aprovado na verificação Dev')
            except discord.Forbidden:
                logger.error('Sem permissão para adicionar cargo %s', CARGO_DEV_VERIFICADO)
                
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
        
        embed_thread = criar_embed_resultado_dev(resultado)
        await self.thread.send(embed=embed_thread)
        
        embed_aprovado = criar_embed_aprovado(user)
        embed_aprovado.add_field(name='Suas Linguagens', value=', '.join(resultado.linguagens_confirmadas), inline=False)
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

    async def _reprovar_dev(self, user: discord.Member, resultado):
        embed = discord.Embed(title='❌  Verificação Reprovada', description=MSG_REPROVADO_AUTO, color=COR_ERRO)
        motivos = '\n'.join((f'• {m}' for m in resultado.motivos_reprovacao))
        embed.add_field(name='Motivos', value=motivos)
        embed.set_footer(text='Você pode tentar novamente em 30 dias. Este chat será apagado em 20 segundos.')
        await self.thread.send(embed=embed)
        logger.info('Usuário %s (%s) REPROVADO automaticamente', user.name, user.id)
        
        import asyncio
        await asyncio.sleep(20)
        try:
            await self.thread.delete()
        except:
            pass

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

def _emoji_experiencia(valor: str) -> str:
    emojis = {'6_meses': '🌱', '1_ano': '📗', '2_anos': '📘', '4_6_anos': '📙', '6_mais': '📕'}
    return emojis.get(valor, '📖')