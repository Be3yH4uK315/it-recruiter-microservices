from aiogram.fsm.state import State, StatesGroup


class EmployerSearch(StatesGroup):
    """FSM состояния для поиска работодателем кандидатов."""

    entering_filters = State()
    main_menu = State()
    showing_results = State()
    entering_company_name = State()
    viewing_list = State()
