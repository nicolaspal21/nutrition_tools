"""
Кастомный SessionService для персистентных сессий в Postgres (Neon).

Назначение: НЕ хранить в БД сырые фото/аудио (inline_data), которые
пользователь шлёт боту. Медиа нужно только в момент распознавания (модель
читает текущий ход из истории сессии), а в долгую историю достаточно
текстового результата (КБЖУ), который агент и так пишет.

Поэтому при записи события в БД медиа-части заменяются на текстовый маркер
вида "[image/jpeg]", а в оперативной (in-memory) сессии байты сохраняются —
чтобы анализ текущего сообщения не сломался.
"""
import logging

from google.genai import types
from google.adk.sessions import DatabaseSessionService

logger = logging.getLogger(__name__)


def _strip_media(content):
    """
    Если в content есть медиа (inline_data) — возвращает
    (parts_без_медиа, исходные_parts). Иначе (None, None).
    """
    if not content or not content.parts:
        return None, None
    if not any(getattr(p, 'inline_data', None) for p in content.parts):
        return None, None

    original_parts = list(content.parts)
    stripped_parts = []
    for part in content.parts:
        if getattr(part, 'inline_data', None):
            mime = part.inline_data.mime_type or 'media'
            stripped_parts.append(types.Part(text=f'[{mime}]'))
        else:
            stripped_parts.append(part)
    return stripped_parts, original_parts


class MediaStrippingDatabaseSessionService(DatabaseSessionService):
    """DatabaseSessionService, который не персистит сырые медиа в БД."""

    async def append_event(self, session, event):
        # Нет контента или нет медиа — обычный путь
        stripped_parts, original_parts = (None, None)
        if event.content:
            stripped_parts, original_parts = _strip_media(event.content)

        if original_parts is None:
            return await super().append_event(session=session, event=event)

        # В БД пишем урезанную версию, в RAM возвращаем байты для текущего хода
        event.content.parts = stripped_parts
        try:
            result = await super().append_event(session=session, event=event)
        finally:
            event.content.parts = original_parts
            if session.events and session.events[-1].content:
                session.events[-1].content.parts = original_parts
        return result
