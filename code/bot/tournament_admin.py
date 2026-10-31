from logging import exception
from unicodedata import category

from aiogram import Router, F
from aiogram.filters import Command, CommandStart, Filter
from aiogram.fsm.context import FSMContext

from aiogram.types import Message, CallbackQuery
from time import perf_counter
import asyncio

import re

import bot.keyboards as kb
from bot.keyboards import CLUB_RATING_BUTTON_DATA, STARS_BUTTON_DATA, MY_ACHIEVMENTS_BUTTON_DATA, \
    PAIR_RATING_BUTTON_DATA
from database.requests import (check_ban, check_event_by_name, add_in_mailing, get_event_info_by_name, check_signup,
                               check_go_to_event, get_full_info_about_singup_user, change_signup_status,
                               add_signup_user,
                               get_count_of_events, check_is_signup_open, get_signup_people, get_user_profile,
                               save_user_profile, get_users_with_polemica_id, get_guest_count_for_event,
                               check_passes_sent, update_user_signups_profile)
from plugins.achievements import get_user_achievements_text, get_club_stars_achievements_text
from plugins.rating import get_club_rating
from plugins.research import get_pair_stat_text
from utils import setup_logger

from database.tournament_requests import *

logger = setup_logger()

tournament_admin = Router()