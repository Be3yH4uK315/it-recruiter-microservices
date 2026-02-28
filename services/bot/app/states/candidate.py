from aiogram.fsm.state import State, StatesGroup

class CandidateFSM(StatesGroup):
    """FSM состояния для кандидата (регистрация и редактирование)."""
    entering_basic_info = State()  # Ввод имени, роли, локации (подшаги в data['current_field'])
    block_entry = State()  # Ввод блоков: опыт, навыки, проекты (data['block_type'], data['current_step'])
    selecting_options = State()  # Выбор: work_modes, skill_kind, skill_level, contacts_visibility
    confirm_action = State()  # Подтверждения: add_another, start_adding (data['action_type'])
    uploading_file = State()  # Загрузка: resume/avatar (data['file_type'])
    choosing_field = State()  # Выбор поля для редактирования
    editing_contacts = State()  # Отдельное для контактов
    showing_profile = State()  # Финальное отображение