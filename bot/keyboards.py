from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


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
