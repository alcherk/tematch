from bot.keyboards import channel_actions_keyboard, feedback_keyboard


def test_feedback_keyboard_has_like_dislike():
    kb = feedback_keyboard(recommendation_id=42)
    buttons = kb.inline_keyboard[0]
    assert len(buttons) == 2
    assert "like" in buttons[0].callback_data
    assert "dislike" in buttons[1].callback_data


def test_channel_actions_keyboard():
    kb = channel_actions_keyboard()
    assert len(kb.inline_keyboard) > 0
