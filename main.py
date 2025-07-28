# --- IMPORTACIONES: Todas las bibliotecas que necesita el bot ---
import discord
from discord.ext import commands
import os
import yt_dlp
import asyncio
from PIL import Image, ImageDraw, ImageFont
import requests
import io
from collections import defaultdict

# --- CONFIGURACIÓN INICIAL DEL BOT ---
# Define los intents (permisos) que tu bot necesita
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.voice_states = True
intents.members = True # <-- IMPORTANTE: Añadido para el evento de bienvenida

# Crea la instancia del bot con un prefijo de comando
bot = commands.Bot(command_prefix='!', intents=intents)

# --- VARIABLES GLOBALES PARA MÚSICA ---
filas_de_reproduccion = {}
opciones_ydl = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

# --- VARIABLES GLOBALES PARA ANTI-SPAM ---
anti_spam = defaultdict(list)
spam_threshold = 5  # Número de mensajes para ser considerado spam
spam_time_window = 10  # En segundos

# --- FUNCIONES AUXILIARES DE MÚSICA ---
def buscar_video(query):
    with yt_dlp.YoutubeDL(opciones_ydl) as ydl:
        try:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)['entries'][0]
        except Exception:
            return None
    return {'url': info['url'], 'title': info['title']}

def reproducir_siguiente(ctx):
    """Función que se llama cuando una canción termina para reproducir la siguiente."""
    if ctx.guild.id in filas_de_reproduccion and filas_de_reproduccion[ctx.guild.id]:
        voice_client = ctx.voice_client
        # Saca la siguiente canción de la lista
        siguiente_cancion = filas_de_reproduccion[ctx.guild.id].pop(0)

        # Opciones para que FFmpeg se reconecte si la conexión falla
        opciones_ffmpeg = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn',
        }

        # Empieza a reproducirla
        voice_client.play(discord.FFmpegPCMAudio(siguiente_cancion['url'], **opciones_ffmpeg), after=lambda e: reproducir_siguiente(ctx))
        
        # Envía un mensaje con la canción que está sonando
        asyncio.run_coroutine_threadsafe(ctx.send(f'▶️ Ahora suena: **{siguiente_cancion["title"]}**'), bot.loop)

# --- EVENTOS DEL BOT ---

@bot.event
async def on_ready():
    """Se dispara cuando el bot está listo y conectado."""
    print(f'✅ Bot conectado como {bot.user}')
    # Registrar Vistas persistentes para que los botones de los tickets sigan funcionando
    bot.add_view(TicketView())
    bot.add_view(CloseTicketView())
    # Sincronizar los comandos de barra diagonal (/) como /crear_mensaje
    await bot.tree.sync()

@bot.event
async def on_member_join(member):
      # Asignar un rol automáticamente
    # Busca un rol llamado "Miembros". ¡Asegúrate de que existe!
    role = discord.utils.get(member.guild.roles, name='Romano')
    if role is not None:
        await member.add_roles(role)
    """TU CÓDIGO DE BIENVENIDA CON IMAGEN (¡Ya integrado!)"""
    channel = discord.utils.get(member.guild.text_channels, name='⌈🛬⌉᲼bienvenida')
    if channel is None:
        return

    try:
        fondo = Image.open("fondo_bienvenida.png").convert("RGBA")
        ancho_fondo, alto_fondo = fondo.size
        response = requests.get(member.avatar.url, stream=True)
        avatar = Image.open(io.BytesIO(response.content)).convert("RGBA")
        tamano_avatar = (150, 150)
        avatar = avatar.resize(tamano_avatar)
        mascara = Image.new("L", tamano_avatar, 0)
        dibujo_mascara = ImageDraw.Draw(mascara)
        dibujo_mascara.ellipse((0, 0) + tamano_avatar, fill=255)
        posicion_x = (ancho_fondo - tamano_avatar[0]) // 2
        posicion_y = 40
        fondo.paste(avatar, (posicion_x, posicion_y), mascara)
        buffer_salida = io.BytesIO()
        fondo.save(buffer_salida, format="PNG")
        buffer_salida.seek(0)
        
        await channel.send(
            content=f"¡Bienvenido al servidor, {member.mention}! 🎉",
            file=discord.File(buffer_salida, "bienvenida_final.png")
        )
    except Exception as e:
        print(f"Ocurrió un error al crear la imagen de bienvenida: {e}")

@bot.event
async def on_message(message):
    """Se dispara cada vez que se envía un mensaje."""
    if message.author.bot:
        return

    # --- SISTEMA ANTI-SPAM ---
    now = message.created_at.timestamp()
    anti_spam[message.author.id].append(now)
    
    # Eliminar timestamps antiguos
    anti_spam[message.author.id] = [t for t in anti_spam[message.author.id] if now - t < spam_time_window]

    if len(anti_spam[message.author.id]) > spam_threshold:
        try:
            await message.channel.send(f'{message.author.mention}, por favor, no hagas spam.', delete_after=5)
            # Opcional: eliminar los mensajes de spam
            await message.channel.purge(limit=spam_threshold, check=lambda m: m.author == message.author)
        except discord.Forbidden:
            pass  # El bot no tiene permisos para borrar mensajes

    await bot.process_commands(message)

# --- COMANDOS DE MODERACIÓN (¡Ya integrados!) ---

@bot.command(name='kick', help='Expulsa a un miembro del servidor.')
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason: str = "No se especificó una razón"):
    await member.kick(reason=reason)
    await ctx.send(f'👢 **{member.display_name}** ha sido expulsado. Razón: {reason}')

@bot.command(name='ban', help='Banea a un miembro del servidor.')
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason: str = "No se especificó una razón"):
    await member.ban(reason=reason)
    await ctx.send(f'🚫 **{member.display_name}** ha sido baneado permanentemente. Razón: {reason}')

@bot.command(name='clean', help='Borra todos los mensajes de un canal.')
@commands.has_any_role("Moderador", "Fundador")
async def clean(ctx):
    """Borra todos los mensajes del canal donde se usa el comando."""
    await ctx.send("Limpiando el canal...")
    await asyncio.sleep(2)
    await ctx.channel.purge()
    await ctx.send("✅ ¡Canal limpiado!", delete_after=5)

# --- COMANDOS DE INFORMACIÓN ---
@bot.command(name='ip', help='Muestra la IP del servidor.')
async def ip(ctx):
    if ctx.channel.name == '⌈❗⌉᲼comandos':
        await ctx.send('La IP es **168.119.88.170:50870**')
    else:
        await ctx.send('Este comando solo se puede usar en el canal `⌈❗⌉᲼comandos`.', delete_after=10)
        await ctx.message.delete()
# --- COMANDOS DE MÚSICA ---

@bot.command(name='join', help='El bot se une a tu canal de voz.')
async def join(ctx):
    if not ctx.author.voice:
        await ctx.send(f'{ctx.author.name}, ¡no estás conectado a un canal de voz! 🗣️')
        return
    channel = ctx.author.voice.channel
    await channel.connect()
    await ctx.send(f'¡Hola! Me he unido a **{channel.name}** 👋')

@bot.command(name='leave', help='El bot abandona el canal de voz.')
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send('¡Adiós! 👋')
        # Limpiar la cola de ese servidor
        if ctx.guild.id in filas_de_reproduccion:
            del filas_de_reproduccion[ctx.guild.id]
    else:
        await ctx.send('No estoy en ningún canal de voz. 🤔')

@bot.command(name='play', help='Reproduce una canción de YouTube.')
async def play(ctx, *, query: str):
    if not ctx.voice_client:
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()
        else:
            await ctx.send("Debes estar en un canal de voz para usar este comando.")
            return

    await ctx.send(f'🔎 Buscando "**{query}**"...')
    cancion = buscar_video(query)
    if cancion is None:
        await ctx.send('No he podido encontrar la canción. 😞')
        return

    if ctx.guild.id not in filas_de_reproduccion:
        filas_de_reproduccion[ctx.guild.id] = []
    filas_de_reproduccion[ctx.guild.id].append(cancion)
    await ctx.send(f'✅ Añadido a la cola: **{cancion["title"]}**')

    if not ctx.voice_client.is_playing():
        reproducir_siguiente(ctx)

@bot.command(name='skip', help='Salta a la siguiente canción en la cola.')
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send('⏭️ Canción saltada.')
    else:
        await ctx.send('No hay ninguna canción sonando ahora mismo.')

# --- SISTEMA DE TICKETS ---

# --- NOMBRES DE LOS ROLES (Configurable) ---
NOMBRE_ROL_SOPORTE = "Soporte"
NOMBRE_ROL_MODERADOR = "Moderador"
NOMBRE_ROL_FUNDADOR = "Fundador"

# --- Vista para el botón de cerrar ticket ---
class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='Cerrar Ticket', style=discord.ButtonStyle.red, emoji='🔒', custom_id='close_ticket_button')
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("El ticket se cerrará en 5 segundos...", ephemeral=True)
        await asyncio.sleep(5)
        await interaction.channel.delete()

# --- Vista para los botones de creación de tickets ---
class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def crear_ticket(self, interaction: discord.Interaction, tipo_ticket: str):
        await interaction.response.send_message(f"Creando tu ticket de {tipo_ticket}...", ephemeral=True)

        guild = interaction.guild
        user = interaction.user

        # --- Obtener los roles desde el servidor ---
        rol_soporte = discord.utils.get(guild.roles, name=NOMBRE_ROL_SOPORTE)
        rol_moderador = discord.utils.get(guild.roles, name=NOMBRE_ROL_MODERADOR)
        rol_fundador = discord.utils.get(guild.roles, name=NOMBRE_ROL_FUNDADOR)

        # Comprobar que los roles básicos existen
        if not rol_moderador or not rol_fundador:
            await interaction.followup.send("Error: Faltan los roles 'Moderador' o 'Fundador'. Avisa a un administrador.", ephemeral=True)
            return

        # --- Construir los permisos dinámicamente ---
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            rol_fundador: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        # Añadir permisos según el tipo de ticket
        if tipo_ticket == "Soporte":
            if rol_soporte:
                overwrites[rol_soporte] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            if rol_moderador:
                overwrites[rol_moderador] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        elif tipo_ticket == "Moderación":
            if rol_moderador:
                overwrites[rol_moderador] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        elif tipo_ticket == "Bugs":
            if rol_moderador:
                overwrites[rol_moderador] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        # --- Crear el canal del ticket ---
        nombre_canal = f"ticket-{user.name}-{tipo_ticket.lower()}"
        canal_ticket = await guild.create_text_channel(
            name=nombre_canal,
            overwrites=overwrites,
            topic=f"Ticket de {user.name} para {tipo_ticket}. Creado el {discord.utils.utcnow().strftime('%d/%m/%Y %H:%M')}"
        )
        
        embed = discord.Embed(
            title=f"Ticket de {tipo_ticket} Creado",
            description=f"Hola {user.mention}, gracias por contactarnos. Un miembro del equipo te atenderá lo antes posible.",
            color=discord.Color.green()
        )
        await canal_ticket.send(embed=embed, view=CloseTicketView())

    # --- Botones ---
    @discord.ui.button(label='Soporte', style=discord.ButtonStyle.secondary, emoji='🧡', custom_id='ticket_support_button')
    async def support_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.crear_ticket(interaction, "Soporte")

    @discord.ui.button(label='Moderación', style=discord.ButtonStyle.secondary, emoji='❤️', custom_id='ticket_moderation_button')
    async def moderation_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.crear_ticket(interaction, "Moderación")

    @discord.ui.button(label='Bugs', style=discord.ButtonStyle.primary, emoji='🐛', custom_id='ticket_bugs_button')
    async def bugs_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.crear_ticket(interaction, "Bugs")

# --- Comando para configurar el panel de tickets ---
@bot.command(name='setup_tickets', help='Crea el panel para que los usuarios abran tickets.')
@commands.has_permissions(administrator=True)
async def setup_tickets(ctx):
    embed = discord.Embed(
        title="Centro de Soporte",
        description="Si necesitas asistencia, te invitamos a crear un ticket. \n\n"
                    "Simplemente selecciona entre los botones de debajo de este mensaje para empezar.",
        color=discord.Color.blue()
    )
    embed.add_field(name="🧡 Soporte", value="Dudas y asistencia general.", inline=False)
    embed.add_field(name="❤️ Moderación", value="Reportes de usuarios.", inline=False)
    embed.add_field(name="🐛 Bugs", value="Asistencia técnica y reportes de errores.", inline=False)
    
    await ctx.send(embed=embed, view=TicketView())
    await ctx.message.delete()

# --- SISTEMA DE MENSAJES PERSONALIZADOS ---

# Modal (ventana emergente) para crear mensajes personalizados
class MessageModal(discord.ui.Modal, title='Crear Mensaje Personalizado'):
    titulo = discord.ui.TextInput(
        label='Título',
        placeholder='Escribe el título principal aquí...',
        style=discord.TextStyle.short,
        required=True
    )
    descripcion = discord.ui.TextInput(
        label='Descripción',
        placeholder='Escribe el texto principal del mensaje. Puedes usar markdown de Discord (ej. **negrita**, - listas).',
        style=discord.TextStyle.paragraph,
        required=True
    )
    imagen_url = discord.ui.TextInput(
        label='URL de la Imagen (Opcional)',
        placeholder='Pega aquí el enlace directo a una imagen (https://...). Déjalo en blanco si no quieres imagen.',
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Primero, confirmamos la interacción de forma oculta
        await interaction.response.defer(ephemeral=True)

        # Creamos el embed con los datos del formulario
        embed = discord.Embed(
            title=self.titulo.value,
            description=self.descripcion.value,
            color=discord.Color(0x000001) # Color negro
        )

        # Si el usuario ha puesto una URL de imagen, la añadimos
        if self.imagen_url.value:
            embed.set_image(url=self.imagen_url.value)

        # Finalmente, enviamos el mensaje como un 'follow-up' al canal
        await interaction.followup.send(embed=embed)


# Comando de barra diagonal (/) para invocar el Modal
@bot.tree.command(name='crear_mensaje', description='Abre un menú para crear un mensaje personalizado.')
@commands.has_permissions(administrator=True)
async def crear_mensaje(interaction: discord.Interaction):
    await interaction.response.send_modal(MessageModal())


# --- INICIAR EL BOT ---
# Pega aquí tu token de Discord
bot.run(os.getenv("DISCORD_TOKEN"))
