import threading
import os
import json
import discord
from discord.ext import commands
from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "bot is running"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web).start()

# ===== 設定 =====
TOKEN = os.getenv("TOKEN")
DATA_FILE = "count.json"

# ===== Intents =====
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ===== データ読み込み =====
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        counts = json.load(f)
else:
    counts = {}

# ===== Utility =====
def save():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(counts, f, ensure_ascii=False, indent=2)

def init_user(guild, member):
    gid = str(guild.id)
    uid = str(member.id)

    # サーバーが未登録なら作成
    if gid not in counts:
        counts[gid] = {}

    # ユーザーが未登録なら作成
    default = {
        "name": member.display_name,
        "ct": 0,
        "ticket": 0,
        "96f": 0,
        "100f": 0
    }

    if uid not in counts[gid]:
        counts[gid][uid] = default.copy()
    else:
        # 不足キーを補完
        for k, v in default.items():
            if k not in counts[gid][uid]:
                counts[gid][uid][k] = v

        counts[gid][uid]["name"] = member.display_name


def get_target(ctx, user):
    return user if user else ctx.author


# ===== Commands =====

@bot.command()
async def ct(ctx, user: discord.Member = None):
    target = get_target(ctx, user)
    init_user(ctx.guild, target)
    d = counts[str(ctx.guild.id)][str(target.id)]

    d["ct"] += 1

    gained = 0
    while d["ct"] >= 5:
        d["ct"] -= 5
        d["ticket"] += 1
        gained += 1

    save()

    msg = f"🎫 CT +1（{target.display_name}）"
    if gained:
        msg += f"\n🎟 クリチケ +{gained}（CT5回分）"

    await ctx.send(msg)

# ---- 96〜99 共通処理 ----

async def add_f96(ctx, user):
    target = get_target(ctx, user)
    init_user(ctx.guild, target)
    counts[str(ctx.guild.id)][str(target.id)]["96f"] += 1
    save()
    await ctx.send(f"💰 96-99ファンブル +1（{target.display_name}）")

@bot.command(name="96f")
async def f96(ctx, user: discord.Member = None):
    await add_f96(ctx, user)

@bot.command(name="97f")
async def f97(ctx, user: discord.Member = None):
    await add_f96(ctx, user)

@bot.command(name="98f")
async def f98(ctx, user: discord.Member = None):
    await add_f96(ctx, user)

@bot.command(name="99f")
async def f99(ctx, user: discord.Member = None):
    await add_f96(ctx, user)

@bot.command(name="100f")
async def f100(ctx, user: discord.Member = None):
    target = get_target(ctx, user)
    init_user(ctx.guild, target)
    counts[str(ctx.guild.id)][str(target.id)]["100f"] += 1
    save()
    await ctx.send(f"💸 100ファンブル +1（{target.display_name}）")

@bot.command()
async def sub(ctx, kind: str, amount: int, user: discord.Member = None):
    target = get_target(ctx, user)
    init_user(ctx.guild, target)
    d = counts[str(ctx.guild.id)][str(target.id)]

    if amount <= 0:
        await ctx.send("数は1以上で指定してね。")
        return

    if kind == "ct":
        d["ct"] = max(0, d["ct"] - amount)
    elif kind == "ticket":
        d["ticket"] = max(0, d["ticket"] - amount)
    elif kind in ["96", "97", "98", "99"]:
        d["96f"] = max(0, d["96f"] - amount)
    elif kind == "100":
        d["100f"] = max(0, d["100f"] - amount)
    else:
        await ctx.send("ct / ticket / 96 / 100 のどれかだよ。")
        return

    save()
    await ctx.send(f"🔽 {kind} を {amount} 減らしたよ！（{target.display_name}）")

@bot.command(name="count")
async def count_cmd(ctx, user: discord.Member = None):
    gid = str(ctx.guild.id)
    print("DEBUG counts =", counts)

    if gid not in counts or not counts[gid]:
        await ctx.send("このサーバーにはまだデータがないようだね。")
        return

    # @ユーザー指定 → その人だけ
    if user:
        uid = str(user.id)
        if uid not in counts[gid]:
            await ctx.send(f"{user.display_name} のデータはまだないようだね。")
            return

        d = counts[gid][uid]

        embed = discord.Embed(
            title=f"📊 {user.display_name} のダイス集計",
            color=0xC8A2C8
        )

        embed.add_field(
            name=d["name"],
            value=(
                f"🎫 CT：{d['ct']}\n"
                f"🎟 クリチケ：{d['ticket']}\n"
                f"💰 96-99：{d['96f']}\n"
                f"💸 100：{d['100f']}"
            ),
            inline=False
        )

        await ctx.send(embed=embed)
        return

    # ============================
    # ここから全員表示（関数の中）
    # ============================

    embed = discord.Embed(
        title="📊 ダイス集計",
        description="（チャンネル別・ユーザー別）",
        color=0xC8A2C8
    )

    for d in sorted(counts[gid].values(), key=lambda x: x["name"]):
        lines = []

        ct = d.get("ct", d.get("crit_1_5", 0))
        f96 = d.get("96f", d.get("fumble_96_99", 0))
        f100 = d.get("100f", d.get("fumble_100", 0))
        ticket = d.get("ticket", 0)

        if ct > 0:
            lines.append(f"🎫 クリティカル(1-5)：{ct}")
        if f96 > 0:
            lines.append(f"💰 ファンブル(96-99)：{f96}")
        if f100 > 0:
            lines.append(f"💸 ファンブル(100)：{f100}")
        if ticket > 0:
            lines.append(f"🎟 クリチケ：{ticket}")

        if not lines:
            continue

        embed.add_field(
            name=d["name"],
            value="\n".join(lines),
            inline=False
        )

    await ctx.send(embed=embed)

import random

@bot.event
async def on_message(message):
    # Bot自身のメッセージには反応しない
    if message.author.bot:
        return

    # ランダム返信リスト
    replies = [
        "ボクを呼んだかい？",
        "やぁやぁ！ボクだよ！",
        "よく言われるよ。",
        "はは！ボクの事だろう？",
        "それは周知の事実じゃないか。",
        "ボクの事だね！"
    ]

    # 「天才」が含まれていたらランダム返信
    if "天才" in message.content:
        await message.channel.send(random.choice(replies))

    # コマンドを動かすために必要
    await bot.process_commands(message)


# ===== Run =====
bot.run(TOKEN)




