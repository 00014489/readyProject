from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder  # Import builder to help adjust rows of buttons
import data.connection as dataPostgres
    
async def percent_choose(file_id: str):
    """
    Creates an InlineKeyboardMarkup with buttons for 0% and 15% vocal mix options.

    :param file_id: The ID of the file being processed, used in callback data.
    :return: InlineKeyboardMarkup object with buttons in rows of 2.
    """
    # Initialize the InlineKeyboardBuilder
    keyboard = InlineKeyboardBuilder()
    id = await dataPostgres.get_id_by_file_id(file_id)
    # Add two buttons: one for 0% vocals and one for 15% vocals
    keyboard.add(
        InlineKeyboardButton(text="0%", callback_data=f"mix_vocals:{id}:0"),
        InlineKeyboardButton(text="15%", callback_data=f"mix_vocals:{id}:15"),
        InlineKeyboardButton(text="50%", callback_data=f"mix_vocals:{id}:50")
    )

    # Adjust the buttons in rows of 2
    return keyboard.adjust(2).as_markup()
