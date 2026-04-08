ROLE_CANDIDATE = "candidate"
ROLE_EMPLOYER = "employer"

DECISION_LIKE = "like"
DECISION_DISLIKE = "dislike"
DECISION_SKIP = "skip"

CONTACT_VISIBILITY_PUBLIC = "public"
CONTACT_VISIBILITY_ON_REQUEST = "on_request"
CONTACT_VISIBILITY_HIDDEN = "hidden"

EMPLOYER_SEARCH_TITLE_MIN_LEN = 3
EMPLOYER_SEARCH_TITLE_MAX_LEN = 120
EMPLOYER_SEARCH_ROLE_MIN_LEN = 2
EMPLOYER_SEARCH_ROLE_MAX_LEN = 120
EMPLOYER_SEARCH_ABOUT_MAX_LEN = 700
WIZARD_SCREEN_MESSAGE_ID_KEY = "_wizard_message_id"
DEFAULT_LIST_PAGE_SIZE = 7

CURRENCY_SYMBOLS = {"RUB": "₽", "USD": "$", "EUR": "€"}
SEARCH_STATUS_LABELS = {
    "active": "🟢 Активен",
    "open": "🟢 Активен",
    "running": "🟢 Активен",
    "paused": "🟡 На паузе",
    "closed": "⚫ Закрыт",
    "archived": "🗄 В архиве",
    "completed": "✅ Завершен",
}

DRAFT_CONFLICT_NAV_ACTIONS = {
    "select_role",
    "candidate_menu_dashboard",
    "candidate_menu_profile",
    "candidate_menu_profile_edit_menu",
    "candidate_menu_open_edit_section",
    "candidate_menu_open_files_section",
    "candidate_menu_open_contacts_section",
    "candidate_menu_stats",
    "candidate_menu_contact_requests",
    "candidate_menu_help",
    "candidate_menu_switch_role",
    "employer_menu_dashboard",
    "employer_menu_profile",
    "employer_menu_open_edit_section",
    "employer_menu_open_files_section",
    "employer_menu_open_search_section",
    "employer_menu_continue_active_search",
    "employer_menu_list_searches",
    "employer_menu_favorites",
    "employer_menu_unlocked_contacts",
    "employer_menu_stats",
    "employer_menu_help",
    "employer_menu_switch_role",
    "employer_menu_create_search",
}
