# core functionality

import discord
import time
import globals
from discord.ext import commands
from typing import Optional
from chain import chat, ConversationCache


class Core(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    async def chat_and_save(self, local_chain: ConversationCache, input: str) -> tuple[str, str]:
        thought_chain =  globals.DISCUSS_THOUGHT_CHAIN if local_chain.conversation_type == "discuss" else globals.WORKSHOP_THOUGHT_CHAIN
        response_chain = globals.DISCUSS_RESPONSE_CHAIN if local_chain.conversation_type == "discuss" else globals.WORKSHOP_RESPONSE_CHAIN
        # response_chain = local_chain.conversation_type == "discuss" ? globals.DISCUSS_RESPONSE_CHAIN : globals.WORKSHOP_RESPONSE_CHAIN
        
        thought = await chat(
            context=local_chain.context,
            inp=input,
            thought_chain=thought_chain,
            thought_memory=local_chain.thought_memory
        )
        response = await chat(
            context=local_chain.context,
            inp=input,
            thought=thought,
            response_chain=response_chain,
            response_memory=local_chain.response_memory
        )
        local_chain.thought_memory.save_context({"input":input}, {"output": thought})
        local_chain.response_memory.save_context({"input":input}, {"output": response})
        return thought, response

    @commands.Cog.listener()
    async def on_ready(self):
        await self.bot.sync_commands()
        print(f"We have logged in as {self.bot.user}: ID = {self.bot.user.id}")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        welcome_message = """
Hello! Thanks for joining the Bloom server. 

I’m your literacy tutor — bring me something you’re reading or writing and paste it in after the `/context` slash command. Then just click the button that lets me know what kind of context you gave me, and I’ll start the conversation. You can reply normally, and I’ll always respond!

Wanna talk about something else? Paste in the new text using the same `/context` command.

Need to leave or just done chatting? Let me know! I’m conversational by design so I’ll say goodbye 😊.

If you have any further questions, feel free to post them in https://discord.com/channels/1076192451997474938/1092832830159065128 and someone from the Plastic Labs team will get back to you ASAP!

Enjoy!
        """
        await member.send(welcome_message)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        # check that the edit actually changed things first
        if before.content != after.content:
            # check that the edit contains a *mention* of the bot
            if str(self.bot.user.id) in after.content:
                LOCAL_CHAIN = globals.CACHE.get(after.channel.id)
                if LOCAL_CHAIN is None:
                    LOCAL_CHAIN = ConversationCache()
                    globals.CACHE.put(after.channel.id, LOCAL_CHAIN)

                i = after.content.replace(str('<@' + str(self.bot.user.id) + '>'), '')
                if LOCAL_CHAIN.context is None:
                    await after.channel.send('Please set a context using `/context`')
                    return
                start = time.time()
                async with after.channel.typing():
                    thought, response = await self.chat_and_save(LOCAL_CHAIN, i)

                thought_channel = self.bot.get_channel(int(globals.THOUGHT_CHANNEL))
                link = f"https://discord.com/channels/{after.guild.id}/{after.channel.id}/{after.id}"
                await thought_channel.send(f"{link}\n```\nThought: {thought}\n```")

                await after.reply(response)

                end = time.time()
                print(f"Link: {link}")
                print(f"Input: {i}")
                print(f"Thought: {thought}")
                print(f"Response: {response}")
                print(f"Elapsed: {end - start}")
                print("=========================================")

    @commands.slash_command(description="Restart the conversation with the tutor")
    async def restart(self, ctx: discord.ApplicationContext, respond: Optional[bool] = True):
        """
        Clears the conversation history and reloads the chains

        Args:
            ctx: context, necessary for bot commands
        """
        LOCAL_CHAIN = globals.CACHE.get(ctx.channel_id)
        if LOCAL_CHAIN:
            LOCAL_CHAIN.restart()
        else:
            LOCAL_CHAIN = ConversationCache()
            globals.CACHE.put(ctx.channel_id, LOCAL_CHAIN )
        # globals.restart()

        if respond:
            msg = "Great! The conversation has been restarted. What would you like to talk about?"
            LOCAL_CHAIN.response_memory.chat_memory.add_ai_message(msg)
            await ctx.respond(msg)
        else:
            return
        
    @commands.slash_command(description="Help using the bot")
    async def help(self, ctx: discord.ApplicationContext):
        """
        Displays help message
        """
        help_message = """
Bloom is your reading and writing tutor. It needs context to start the conversation. That can be either
            
            1. a passage of reading you're struggling to understand
            2. a snippet of writing you're working on
        
Paste either after the `/context` command and select what you'd like to do. Then just chat!
If you'd like to restart the conversation, use the `/restart` command. Then you can use `/context` again with new context!
If you're still having trouble, drop a message in https://discord.com/channels/1076192451997474938/1092832830159065128 and Bloom's builders will help you out!
        """
        await ctx.respond(help_message)


    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return

        # if the message came from a DM channel...
        if isinstance(message.channel, discord.channel.DMChannel):
            LOCAL_CHAIN = globals.CACHE.get(message.channel.id)
            if LOCAL_CHAIN is None:
                LOCAL_CHAIN = ConversationCache()
                globals.CACHE.put(message.channel.id, LOCAL_CHAIN)

            i = message.content.replace(str('<@' + str(self.bot.user.id) + '>'), '')
            if LOCAL_CHAIN.context is None:
                await message.channel.send('Please set a context using `/context`')
                return
            
            start = time.time()
            async with message.channel.typing():
                thought, response = await self.chat_and_save(LOCAL_CHAIN, i)

            thought_channel = self.bot.get_channel(int(globals.THOUGHT_CHANNEL))
            link = f"DM: {message.author.mention}"
            await thought_channel.send(f"{link}\n```\nInput: {i}\nThought: {thought}\n```")

            await message.channel.send(response)

            end = time.time()
            print(f"DM: {message.author.mention}")
            print(f"Input: {i}")
            print(f"Thought: {thought}")
            print(f"Response: {response}")
            print(f"Elapsed: {end - start}")
            print("=========================================")

        # if the user mentioned the bot outside of DMs...
        if not isinstance(message.channel, discord.channel.DMChannel):
            if str(self.bot.user.id) in message.content:
                LOCAL_CHAIN = globals.CACHE.get(message.channel.id)
                if LOCAL_CHAIN is None:
                    LOCAL_CHAIN = ConversationCache()
                    globals.CACHE.put(message.channel.id, LOCAL_CHAIN)

                i = message.content.replace(str('<@' + str(self.bot.user.id) + '>'), '')
                if LOCAL_CHAIN.context is None:
                    await message.channel.send('Please set a context using `/context`')
                    return
                
                start = time.time()
                async with message.channel.typing():
                    thought, response = await self.chat_and_save(LOCAL_CHAIN, i)

                thought_channel = self.bot.get_channel(int(globals.THOUGHT_CHANNEL))
                link = f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"
                await thought_channel.send(f"{link}\n```\nThought: {thought}\n```")

                await message.reply(response)

                end = time.time()
                print(f"Link: {link}")
                print(f"Input: {i}")
                print(f"Thought: {thought}")
                print(f"Response: {response}")
                print(f"Elapsed: {end - start}")
                print("=========================================")

        # if the user replied to the bot outside of DMs...
        if not isinstance(message.channel, discord.channel.DMChannel):
            if message.reference is not None:
                LOCAL_CHAIN = globals.CACHE.get(message.channel.id)
                if LOCAL_CHAIN is None:
                    LOCAL_CHAIN = ConversationCache()
                    globals.CACHE.put(message.channel.id, LOCAL_CHAIN)
                # and if the referenced message is from the bot...
                reply_msg = await self.bot.get_channel(message.channel.id).fetch_message(message.reference.message_id)
                if reply_msg.author == self.bot.user:
                    i = message.content.replace(str('<@' + str(self.bot.user.id) + '>'), '')
                    # check that the reply isn't to one of the bot's thought messages
                    if reply_msg.content.startswith("https://discord.com"):
                        return
                    if LOCAL_CHAIN.context is None:
                        await message.channel.send('Please set a context using `/context`')
                        return
                    if message.content.startswith("!no") or message.content.startswith("!No"):
                        return
                    start = time.time()
                    async with message.channel.typing():
                        thought, response = await self.chat_and_save(LOCAL_CHAIN, i)

                    thought_channel = self.bot.get_channel(int(globals.THOUGHT_CHANNEL))
                    link = f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"
                    await thought_channel.send(f"{link}\n```\nThought: {thought}\n```")

                    await message.reply(response)

                    end = time.time()
                    print(f"Link: {link}")
                    print(f"Input: {i}")
                    print(f"Thought: {thought}")
                    print(f"Response: {response}")
                    print(f"Elapsed: {end - start}")
                    print("=========================================")

        


def setup(bot):
    bot.add_cog(Core(bot))
