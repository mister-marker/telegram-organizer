"""
Защита от FloodWaitError для всех операций записи (архивация, папки,
мьют, выход из чата).

Telegram НЕ публикует официально точное число запросов в секунду для
методов MTProto — поэтому вместо того, чтобы зашивать в код придуманное
число (условные "20-30 запросов в секунду" из непроверенных источников),
используем два реальных, документированных механизма:

  1. Консервативная пауза между запросами (PACE_SECONDS) — снижает
     вероятность вообще упереться в лимит.
  2. Реактивная обработка FloodWaitError — если лимит всё же превышен,
     Telegram сам присылает точное число секунд ожидания (e.seconds),
     и мы ждём ровно столько, а не наугад.

Это официально задокументированный и единственный надёжный способ
работать с лимитами MTProto, вне зависимости от того, как часто Telegram
меняет реальные пороги.
"""
import asyncio
from telethon.errors import FloodWaitError

PACE_SECONDS = 1.0


async def with_flood_control(coro_factory, *, pace: float = PACE_SECONDS):
    while True:
        try:
            result = await coro_factory()
            await asyncio.sleep(pace)
            return result
        except FloodWaitError as e:
            print(f"[flood-wait] Telegram просит подождать {e.seconds} сек. Ждём...")
            await asyncio.sleep(e.seconds + 1)
