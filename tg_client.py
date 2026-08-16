"""
Подключение к Telegram через Telethon (MTProto-клиент, "юзербот").

Почему не Bot API: официальный Bot API технически не может увидеть ни ваш
личный список диалогов, ни ваши папки — боты живут в собственном простран-
стве и никогда не имеют доступа к аккаунту обычного пользователя (это
архитектурное разделение самого Telegram, а не наше ограничение). Единст-
венный путь получить доступ к своим же диалогам и папкам — авторизовать
MTProto-клиент под своим номером телефона, как это делает обычное
приложение (Desktop/Android/iOS). Telethon именно это и делает.

Важно про риски: автоматизация личного аккаунта через MTProto-библиотеки
(Telethon/Pyrogram/GramJS) — серая зона Terms of Service Telegram. Офици-
альный текст ToS не содержит слова "userbot", но практика и многочисленные
open-source проекты в этой нише прямо предупреждают: аккаунт может быть
ограничен или заблокирован, если поведение похоже на спам/накрутку/масс-
рассылку. Для сценария "читать метаданные своих же диалогов и раскладывать
их по папкам" риск существенно ниже, чем для массовых рассылок, но он не
нулевой — Telegram нигде явно не гарантирует безопасность такого использо-
вания. Подробнее — в README, раздел "Безопасность".

С Этапа 2 сессия больше не хранится в файле *.session. Вместо этого
используется Telethon StringSession: клиент получает session-string из
macOS Keychain, держит её в памяти во время работы, а после успешного
логина сохраняет обновлённую строку обратно в Keychain.
"""
from telethon import TelegramClient
from config import Settings
from device_fingerprint import build_device_fingerprint
from session_vault import load_string_session, save_client_session


def legacy_session_path(settings: Settings) -> str:
    return f"{settings.session_name}.session"


def build_client(settings: Settings) -> TelegramClient:
    """
    Собрать Telethon-клиент без файлового session storage.

    Важная деталь Telethon: первый аргумент TelegramClient может быть не
    именем файла, а объектом сессии. Когда мы передаём StringSession, Telethon
    не создаёт `tg_organizer.session` рядом с кодом; он работает с сессией в
    памяти, а постоянное хранение полностью контролирует session_vault.py.

    Device fingerprint передаётся как metadata MTProto initConnection. Эти
    поля показывают Telegram, с какого класса устройства и приложения пришло
    подключение. Мы держим их рядом с созданием клиента, потому что после
    авторизации менять этот отпечаток на лету уже поздно: он участвует именно
    в установке MTProto-соединения.
    """
    fingerprint = build_device_fingerprint(settings)
    return TelegramClient(
        load_string_session(settings),
        settings.api_id,
        settings.api_hash,
        **fingerprint.as_telethon_kwargs(),
    )


async def ensure_started(client: TelegramClient, settings: Settings) -> None:
    """
    При первом запуске Telethon интерактивно запросит номер телефона, код
    из Telegram и, если включена двухфакторная аутентификация, облачный
    пароль — как обычный вход в новое приложение.

    После успешного start() Telethon уже держит актуальную StringSession в
    client.session. Мы сразу сохраняем её в Keychain. Это закрывает окно, где
    пользователь вошёл в аккаунт, но безопасное постоянное хранилище ещё не
    обновлено.
    """
    await client.start()
    save_client_session(settings, client)
    me = await client.get_me()
    username = f"@{me.username}" if me.username else "без username"
    print(f"[ok] Авторизованы как: {me.first_name} ({username}); сессия сохранена в macOS Keychain")
