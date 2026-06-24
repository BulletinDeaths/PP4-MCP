import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _is_within_workspace(file_path: str, workspace_dir: str) -> bool:
    """Проверяет, находится ли путь внутри рабочей директории."""
    workspace_path = Path(workspace_dir).resolve()
    absolute_file_path = Path(file_path).resolve()

    try:
        # .relative_to() вызовет исключение, если paths не связаны
        absolute_file_path.relative_to(workspace_path)
        return True
    except ValueError:
        return False


def write_file(content: str, file_path: str, workspace_dir: str) -> bool:
    """
    Безопасно записывает контент в файл.
    :param content: Строка для записи.
    :param file_path: Относительный путь к файлу от корня workspace.
    :param workspace_dir: Абсолютный путь к корневой директории workspace.
    :return: True, если запись успешна, иначе False.
    """
    full_path = os.path.join(workspace_dir, file_path)

    # Защита от выхода за пределы workspace
    if not _is_within_workspace(full_path, workspace_dir):
        logger.error(f"Попытка записи за пределами workspace: {full_path}")
        return False

    try:
        # Создаем все необходимые родительские директории
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)

        logger.info(f"Инструмент: Успешно записан файл '{file_path}'")
        return True
    except OSError as e:
        logger.error(f"Инструмент: Ошибка записи в файл '{file_path}': {e}")
        return False


def create_directory(dir_path: str, workspace_dir: str) -> bool:
    """
    Создает директорию внутри workspace.
    :param dir_path: Относительный путь к директории от корня workspace.
    :param workspace_dir: Абсолютный путь к корневой директории workspace.
    :return: True, если создание успешно, иначе False.
    """
    full_path = os.path.join(workspace_dir, dir_path)

    if not _is_within_workspace(full_path, workspace_dir):
        logger.error(f"Попытка создания директории за пределами workspace: {full_path}")
        return False

    try:
        os.makedirs(full_path, exist_ok=True)
        logger.info(f"Инструмент: Успешно создана директория '{dir_path}'")
        return True
    except OSError as e:
        logger.error(f"Инструмент: Ошибка создания директории '{dir_path}': {e}")
        return False