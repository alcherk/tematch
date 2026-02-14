from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

if TYPE_CHECKING:
    from bot.formatters import DigestItem


def feedback_keyboard(recommendation_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="\U0001f44d", callback_data=f"fb:like:{recommendation_id}"
                ),
                InlineKeyboardButton(
                    text="\U0001f44e",
                    callback_data=f"fb:dislike:{recommendation_id}",
                ),
            ]
        ]
    )


def digest_keyboard(items: list[DigestItem]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    current_row: list[InlineKeyboardButton] = []

    for item in items:
        current_row.extend([
            InlineKeyboardButton(
                text=f"{item.index}\U0001f44d",
                callback_data=f"fb:like:{item.rec_id}",
            ),
            InlineKeyboardButton(
                text=f"{item.index}\U0001f44e",
                callback_data=f"fb:dislike:{item.rec_id}",
            ),
        ])
        # 3 pairs (6 buttons) per row
        if len(current_row) >= 6:
            rows.append(current_row)
            current_row = []

    if current_row:
        rows.append(current_row)

    return InlineKeyboardMarkup(inline_keyboard=rows)


def channel_actions_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Мои каналы",
                    callback_data="channels:list",
                ),
                InlineKeyboardButton(
                    text="Добавить канал",
                    callback_data="channels:add",
                ),
            ]
        ]
    )
