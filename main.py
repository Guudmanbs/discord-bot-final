# --- IMPORTACIONES: Todas las bibliotecas que necesita el bot ---
import discord
from discord.ext import commands
import os
import yt_dlp
import asyncio
from PIL import Image, ImageDraw, ImageFont
import requests
import io

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
        # ESTA LÍNEA DEBE ESTAR ALINEADA CON LA ANTERIOR
        asyncio.run_coroutine_threadsafe(ctx.send(f'▶️ Ahora suena: **{siguiente_cancion["title"]}**'), bot.loop)

# --- EVENTOS DEL BOT ---

@bot.event
async def on_ready():
    """Se dispara cuando el bot está listo y conectado."""
    print(f'✅ Bot conectado como {bot.user}')

@bot.event
async def on_member_join(member):
      # Asignar un rol automáticamente
    # Busca un rol llamado "Miembros". ¡Asegúrate de que existe!
    role = discord.utils.get(member.guild.roles, name='Romano')
    if role is not None:
        await member.add_roles(role)
    """TU CÓDIGO DE BIENVENIDA CON IMAGEN (¡Ya integrado!)"""
    channel = discord.utils.get(member.guild.text_channels, name='bienvenida')
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


# --- INICIAR EL BOT ---
# Pega aquí tu token de Discord
bot.run(os.getenv("DISCORD_TOKEN"))