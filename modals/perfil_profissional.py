import logging
import asyncio
import discord
from discord.ui import Modal, TextInput
from config.settings import COR_PRINCIPAL, COR_SUCESSO, COR_ALERTA, COR_ERRO, CARGO_DEV_VERIFICADO, CARGOS_LINGUAGEM, CANAL_DIAGNOSTICO_DEV, CANAL_STAFF_REVIEW, MSG_PROCESSANDO, MSG_APROVADO, MSG_REVIEW
from services.github_service import buscar_perfil_github
from services.linkedin_service import verificar_linkedin
from services.scoring_service import calcular_score
from embeds.diagnostico_embed import criar_embed_diagnostico
from embeds.review_embed import criar_embed_review
from utils.helpers import extrair_username_github, extrair_username_linkedin, experiencia_label
logger = logging.getLogger('bot_freeela.modals.perfil_profissional')

class PerfilProfissionalModal(Modal, title='Perfil Profissional — Etapa 3'):
    github = TextInput(label='GitHub (obrigatório)', style=discord.TextStyle.short, placeholder='https://github.com/seu-usuario', required=True, max_length=200)
    linkedin = TextInput(label='LinkedIn (obrigatório)', style=discord.TextStyle.short, placeholder='https://linkedin.com/in/seu-perfil', required=True, max_length=200)
    descricao = TextInput(label='Descrição profissional (obrigatório)', style=discord.TextStyle.paragraph, placeholder='Ex: Desenvolvo bots em Python, trabalho com automações e estudo backend com Java.', required=True, min_length=20, max_length=500)
    portfolio = TextInput(label='Portfólio / Site pessoal (opcional)', style=discord.TextStyle.short, placeholder='https://seu-site.com', required=False, max_length=200)
    links_extras = TextInput(label='Links extras (opcional)', style=discord.TextStyle.paragraph, placeholder='GitLab, Stack Overflow, Kaggle, Medium, Dev.to...\nUm por linha.', required=False, max_length=500)

    def __init__(self, user_id: int, linguagens: list[str], experiencia: str, thread: discord.Thread):
        super().__init__()
        self.user_id = user_id
        self.linguagens = linguagens
        self.experiencia = experiencia
        self.thread = thread

    async def on_submit(self, interaction: discord.Interaction):
        user = interaction.user
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message('❌ Erro interno.', ephemeral=True)
            return
        embed_processando = discord.Embed(title='⏳  Analisando seu perfil...', description=MSG_PROCESSANDO, color=COR_ALERTA)
        embed_processando.add_field(name='📋  Dados recebidos', value=f"**GitHub:** {self.github.value}\n**LinkedIn:** {self.linkedin.value}\n**Linguagens:** {', '.join(self.linguagens)}\n**Experiência:** {experiencia_label(self.experiencia)}", inline=False)
        await interaction.response.send_message(embed=embed_processando)
        try:
            github_username = extrair_username_github(self.github.value)
            linkedin_username = extrair_username_linkedin(self.linkedin.value)
            if not github_username:
                await self.thread.send(embed=discord.Embed(title='❌  GitHub Inválido', description='Não foi possível extrair o username do GitHub.', color=COR_ERRO))
                return
            github_task = buscar_perfil_github(github_username)
            linkedin_task = verificar_linkedin(linkedin_username or '')
            github_profile, linkedin_profile = await asyncio.gather(github_task, linkedin_task)
            resultado = calcular_score(linguagens_selecionadas=self.linguagens, experiencia=self.experiencia, descricao=self.descricao.value, github_profile=github_profile, linkedin_profile=linkedin_profile)
            github_url = f'https://github.com/{github_username}'
            linkedin_url = f'https://linkedin.com/in/{linkedin_username}' if linkedin_username else ''
            if resultado.aprovado:
                await self._aprovar_usuario(guild=guild, user=user, resultado=resultado, github_url=github_url, linkedin_url=linkedin_url)
            else:
                await self._enviar_review(guild=guild, user=user, resultado=resultado, github_url=github_url, linkedin_url=linkedin_url)
            await self._enviar_diagnostico(guild=guild, user=user, resultado=resultado, github_url=github_url, linkedin_url=linkedin_url)
            await asyncio.sleep(15)
            try:
                await self.thread.edit(archived=True, locked=True)
            except Exception:
                pass
        except Exception as e:
            logger.exception('Erro durante validação para %s: %s', user.name, e)
            await self.thread.send(embed=discord.Embed(title='❌  Erro na Validação', description='Ocorreu um erro durante a análise. A staff foi notificada.', color=COR_ERRO))

    async def _aprovar_usuario(self, guild: discord.Guild, user: discord.Member, resultado, github_url: str, linkedin_url: str):
        membro = guild.get_member(user.id)
        if not membro:
            return
        cargos_atribuidos = []
        cargo_dev = guild.get_role(CARGO_DEV_VERIFICADO)
        if cargo_dev:
            try:
                await membro.add_roles(cargo_dev, reason='Verificação dev aprovada')
                cargos_atribuidos.append('Desenvolvedor Verificado')
            except discord.Forbidden:
                logger.error('Sem permissão para adicionar cargo dev a %s', user.name)
        for lang in resultado.linguagens_confirmadas:
            role_id = CARGOS_LINGUAGEM.get(lang)
            if role_id:
                role = guild.get_role(role_id)
                if role:
                    try:
                        await membro.add_roles(role, reason=f'Linguagem confirmada: {lang}')
                        cargos_atribuidos.append(lang)
                    except discord.Forbidden:
                        logger.error('Sem permissão para adicionar cargo %s a %s', lang, user.name)
        embed = discord.Embed(title='🎉  Aprovado!', description=MSG_APROVADO, color=COR_SUCESSO)
        embed.add_field(name='📈  Compatibilidade', value=f'**{resultado.compatibilidade}%**', inline=True)
        embed.add_field(name='🔒  Integridade', value=f'**{resultado.integridade}%**', inline=True)
        if cargos_atribuidos:
            embed.add_field(name='🏅  Cargos Atribuídos', value='\n'.join((f'• {c}' for c in cargos_atribuidos)), inline=False)
        embed.set_footer(text='Esta thread será arquivada em breve.')
        await self.thread.send(embed=embed)
        logger.info('Usuário %s (%s) APROVADO | compat=%d | integ=%d | cargos=%s', user.name, user.id, resultado.compatibilidade, resultado.integridade, cargos_atribuidos)

    async def _enviar_review(self, guild: discord.Guild, user: discord.Member, resultado, github_url: str, linkedin_url: str):
        embed_thread = discord.Embed(title='📋  Enviado para Revisão', description=MSG_REVIEW, color=COR_ALERTA)
        embed_thread.add_field(name='📈  Compatibilidade', value=f'**{resultado.compatibilidade}%**', inline=True)
        embed_thread.add_field(name='🔒  Integridade', value=f'**{resultado.integridade}%**', inline=True)
        if resultado.motivos_reprovacao:
            embed_thread.add_field(name='📌  Motivos', value='\n'.join((f'• {m}' for m in resultado.motivos_reprovacao)), inline=False)
        embed_thread.set_footer(text='Esta thread será arquivada em breve.')
        await self.thread.send(embed=embed_thread)
        canal_review = guild.get_channel(CANAL_STAFF_REVIEW)
        if canal_review:
            membro = guild.get_member(user.id)
            if membro:
                embed_review = criar_embed_review(usuario=membro, resultado=resultado, github_url=github_url, linkedin_url=linkedin_url, descricao=self.descricao.value, experiencia_label=experiencia_label(self.experiencia))
                await canal_review.send(embed=embed_review)
        logger.info('Usuário %s (%s) enviado para REVIEW | compat=%d | integ=%d', user.name, user.id, resultado.compatibilidade, resultado.integridade)

    async def _enviar_diagnostico(self, guild: discord.Guild, user: discord.Member, resultado, github_url: str, linkedin_url: str):
        canal_diag = guild.get_channel(CANAL_DIAGNOSTICO_DEV)
        if not canal_diag:
            logger.error('Canal diagnostico-dev não encontrado')
            return
        membro = guild.get_member(user.id)
        if not membro:
            return
        embed = criar_embed_diagnostico(usuario=membro, resultado=resultado, github_url=github_url, linkedin_url=linkedin_url)
        await canal_diag.send(embed=embed)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.exception('Erro no modal de perfil: %s', error)
        try:
            await interaction.response.send_message('❌ Ocorreu um erro ao processar o formulário.', ephemeral=True)
        except discord.InteractionResponded:
            await interaction.followup.send('❌ Ocorreu um erro ao processar o formulário.', ephemeral=True)