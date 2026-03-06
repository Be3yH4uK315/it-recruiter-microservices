from aiogram.fsm.state import State, StatesGroup


class EmployerSearch(StatesGroup):
    """FSM состояния для поиска работодателем кандидатов."""

    entering_filters = State()
    showing_results = State()
    entering_company_name = State()
