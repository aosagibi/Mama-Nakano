import discord
import asyncio
import json
import aiohttp
import datetime
from DBService import DBService
from discord.ext import commands
from cogs.OwnerOnly import blacklist_ids
from discord.ext.commands import Bot

server_config_raw = DBService.exec("SELECT * FROM ServerConfig").fetchall()
server_config = dict()

def cache_guild(db_response):
	server_config[db_response[0]] = {'prefix': db_response[1], 'del_commands': True if db_response[2] else False, 'on_reaction': True if db_response[3] else False}

for i in server_config_raw:
	cache_guild(i)

del server_config_raw

with open('configs/config.json') as json_data:
	response_json = json.load(json_data)
	default_prefix = response_json['default_prefix']
	success_string = response_json['response_string']['success']
	error_string = response_json['response_string']['error']
	del response_json 

def quote_embed(context_channel, message, user):
	if not message.content and message.embeds and message.author.bot:
		embed = message.embeds[0]
	else:
		if message.author not in message.guild.members or message.author.color == discord.Colour.default():
			embed = discord.Embed(description = message.content + '\n\n[Lihat chat asli](https://discordapp.com/channels/' + str(message.guild.id) + '/' + str(message.channel.id) + '/' + str(message.id) + ')', timestamp = message.created_at)
		else:
			embed = discord.Embed(description = message.content + '\n\n[Lihat chat asli](https://discordapp.com/channels/' + str(message.guild.id) + '/' + str(message.channel.id) + '/' + str(message.id) + ')', color = message.author.color, timestamp = message.created_at)
		if message.attachments:
			if message.channel.is_nsfw() and not context_channel.is_nsfw():
				embed.add_field(name = 'Attachments', value = ':underage: **Chat ini berada dalam channel NSFW.**')
			elif len(message.attachments) == 1 and message.attachments[0].url.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.gifv', '.webp', '.bmp')):
				embed.set_image(url = message.attachments[0].url)
			else:
				for attachment in message.attachments:
					embed.add_field(name = 'Attachment', value = '[' + attachment.filename + '](' + attachment.url + ')', inline = False)
		embed.set_author(name = str(message.author.display_name), icon_url = message.author.avatar_url)
		if message.channel != context_channel:
			embed.set_footer(text = '#' + message.channel.name)
		else:
			embed.set_footer(text = '#' + message.channel.name)
	return embed

class Main(commands.Cog):
	def __init__(self, bot):
		self.bot = bot

	@commands.Cog.listener()
	async def on_ready(self):
		for guild in self.bot.guilds:
			try:
				DBService.exec("INSERT INTO ServerConfig (Guild) VALUES (" + str(guild.id) + ")")
			except Exception:
				continue

		server_config_raw = DBService.exec("SELECT * FROM ServerConfig").fetchall()
		for i in server_config_raw:
			cache_guild(i)

		guild_ids = [guild.id for guild in self.bot.guilds]
		cached_guilds = [i for i in server_config.keys()]

		for i in cached_guilds:
			if i not in guild_ids:
				del cached_guilds[i]

	@commands.Cog.listener()
	async def on_guild_remove(self, guild):
		try:
			del server_config[guild.id]
		except KeyError:
			pass

	@commands.Cog.listener()
	async def on_guild_join(self, guild):
		try:
			DBService.exec("INSERT INTO ServerConfig (Guild) VALUES (" + str(guild.id) + ")")
		except Exception:
			pass

		db_response = DBService.exec("SELECT * FROM ServerConfig WHERE Guild = " + str(guild.id)).fetchone()
		cache_guild(db_response)

	'''@commands.Cog.listener()
	async def on_command_error(self, ctx, error):
		if isinstance(error, commands.CommandOnCooldown):
			await ctx.send(content = error_string + ' **Please wait ' + str(round(error.retry_after, 1)) + ' seconds before invoking this again.**', delete_after = 5)
'''
	@commands.Cog.listener()
	async def on_raw_reaction_add(self, payload):
		if str(payload.emoji) == '💬' and payload.user_id not in blacklist_ids and not self.bot.get_guild(payload.guild_id).get_member(payload.user_id).bot and server_config[payload.guild_id]['on_reaction']:
			guild = self.bot.get_guild(payload.guild_id)
			channel = guild.get_channel(payload.channel_id)
			user = guild.get_member(payload.user_id)

			if user.permissions_in(channel).send_messages:
				try:
					message = await channel.fetch_message(payload.message_id)
				except discord.NotFound:
					return
				except discord.Forbidden:
					return
				else:
					if not message.content and message.embeds and message.author.bot:
						await channel.send(content = 'Raw embed from `' + str(message.author).strip('`') + '` in ' + message.channel.mention, embed = quote_embed(channel, message, user))
					else:
						await channel.send(embed = quote_embed(channel, message, user))

	@commands.command(aliases = ['q'])
	@commands.cooldown(rate = 2, per = 5, type = commands.BucketType.channel)
	async def quote(self, ctx, msg_arg = None, *, reply = None):
		if not msg_arg:
			return await ctx.send(content = error_string + ' **Maaf, chat tidak ditemukan.**')

		if ctx.guild and server_config[ctx.guild.id]['del_commands'] and ctx.guild.me.permissions_in(ctx.channel).manage_messages:
			await ctx.message.delete()

		message = None
		try:
			msg_arg = int(msg_arg)
		except ValueError:
			perms = ctx.guild.me.permissions_in(ctx.channel)
			if perms.read_messages and perms.read_message_history:
				async for msg in ctx.channel.history(limit = 100, before = ctx.message):
					if msg_arg.lower() in msg.content.lower():
						message = msg
						break
		else:
			try:
				message = await ctx.channel.fetch_message(msg_arg)
			except:
				for channel in ctx.guild.text_channels:
					perms = ctx.guild.me.permissions_in(channel)
					if channel == ctx.channel or not perms.read_messages or not perms.read_message_history:
						continue

					try:
						message = await channel.fetch_message(msg_arg)
					except:
						continue
					else:
						break

		if message:
			if not message.content and message.embeds and message.author.bot:
				await ctx.send(content = 'Embed oleh **' + str(message.author.display_name).strip() + '**', embed = quote_embed(ctx.channel, message, ctx.author))
			else:
				await ctx.send(embed = quote_embed(ctx.channel, message, ctx.author))
			if reply:
				await ctx.send(content = '**' + ctx.author.display_name + '\'s reply:**\n' + reply.replace('@everyone', '@еveryone').replace('@here', '@hеre'))
		else:
			await ctx.send(content = error_string + ' **Maaf, chat tidak ditemukan.**')

	@commands.command(aliases = ['delcmds'])
	@commands.has_permissions(manage_guild = True)
	async def delcommands(self, ctx):
		if not server_config[ctx.guild.id]['del_commands']:

			try:
				DBService.exec("INSERT INTO ServerConfig (Guild, DelCommands) VALUES (" + str(ctx.guild.id) + ", '1')")
			except Exception:
				DBService.exec("UPDATE ServerConfig SET DelCommands = '1' WHERE Guild = " + str(ctx.guild.id))
			server_config[ctx.guild.id]['del_commands'] = True

			await ctx.send(content = success_string + ' **Auto-delete of quote commands enabled.**')

		else:

			DBService.exec("UPDATE ServerConfig SET DelCommands = NULL WHERE Guild = " + str(ctx.guild.id))
			server_config[ctx.guild.id]['del_commands'] = False

			await ctx.send(content = success_string + ' **Auto-delete of quote commands disabled.**')

	@commands.command(pass_context=True)
	async def embed(self, ctx, *, a_sMessage):
    		embed = discord.Embed(description=a_sMessage, color=ctx.author.color)
    		await ctx.send(embed=embed)

	@commands.command()
	async def autoembed(self, ctx):

        # Define a check function that validates the message received by the bot
        	def check(ms):
            # Look for the message sent in the same channel where the command was used
            # As well as by the user who used the command.
            	 return ms.channel == ctx.message.channel and ms.author == ctx.message.author

        # First ask the user for the title
        	await ctx.send(content='Silahkan masukkan **judul** embed.')

        # Wait for a response and get the title
        	msg = await self.bot.wait_for('message', check=check)
        	title = msg.content # Set the title

        # Next, ask for the content
        	await ctx.send(content='Silahkan masukkan **deskripsi** embed.')
        	msg = await self.bot.wait_for('message', check=check)
        	desc = msg.content

        # Finally make the embed and send it
        	msg = await ctx.send(content='Sedang membuat embed...')

        # Convert the colors into a list
        # To be able to use random.choice on it

        	embed = discord.Embed(
            	title=title,
            	description=desc,
            	color=0x3498DB
        	)

        	await msg.edit(
            	embed=embed,
            	content=None
        	)
        # Editing the message
        # We have to specify the content to be 'None' here
        # Since we don't want it to stay to 'Now generating embed...'

        	return

def setup(bot):
	bot.add_cog(Main(bot))