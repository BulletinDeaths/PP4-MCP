import os
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class Agent:
    """
    Агент-разработчик, который принимает структурированное ТЗ в формате JSON
    от агента-аналитика и генерирует рабочие файлы с кодом.
    """

    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.llm_provider = self.orchestrator.shared_memory.get('llm_provider', 'ollama')
        self.prompt_path = os.path.join("workspace", "prompts", "developer.md")
        self.workspace_dir = self.orchestrator.workspace_dir
        self.projects_dir = os.path.join(self.workspace_dir, "projects")

    def handle_message(self) -> str:
        """
        Обрабатывает сообщение из общей памяти. Ожидает найти там JSON-ТЗ,
        сгенерированное AnalystAgent.
        """
        logger.info("Разработчик ищет ТЗ в общей памяти...")

        raw_analyst_result = self.orchestrator.shared_memory.get('analyst_result_raw')

        if not raw_analyst_result:
            return "Ошибка: не найдено техническое задание от агента-аналитика в общей памяти."

        try:
            # Используем json5 для более терпимого к ошибкам парсинга
            import json5
            generated_files_data = json5.loads(raw_analyst_result)

            # Проверяем, что данные имеют ожидаемый формат (СПИСОК файлов)
            if not isinstance(generated_files_data, list):
                raise ValueError("Ответ LLM не является списком файлов.")

            # Создаем корневую директорию проекта, если ее нет
            os.makedirs(self.projects_dir, exist_ok=True)

            # Итерация по каждому файлу из ТЗ и запись на диск
            for file_info in generated_files_data:
                path = file_info.get('path')
                code = file_info.get('code')

                if not path or code is None:
                    logger.warning(f"Пропуск файла из-за неверного формата: {file_info}")
                    continue

                # Формируем полный путь и создаем промежуточные директории
                full_path = os.path.join(self.projects_dir, path)
                directory = os.path.dirname(full_path)
                os.makedirs(directory, exist_ok=True)

                # Записываем код в файл
                with open(full_path, 'w', encoding='utf-8') as code_file:
                    code_file.write(code)

                logger.info(f"Создан файл: {full_path}")

            return f"Успешно сгенерирован проект. Файлы находятся в каталоге: {self.projects_dir}"

        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON от LLM: {e}")
            return "Ошибка: Ответ от языковой модели имеет неверный формат JSON."
        except Exception as e:
            logger.exception(f"Неожиданная ошибка при работе агента-разработчика: {e}")
            return f"Произошла непредвиденная ошибка: {str(e)}"