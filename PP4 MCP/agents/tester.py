import os
import json
import requests
from pathlib import Path


class TesterAgent:
    def __init__(self, project_name):
        """
        :param project_name: Имя папки проекта внутри workspace/projects/
        """
        self.project_dir = Path("workspace") / "projects" / project_name
        self.tests_dir = self.project_dir / "tests"
        self.prompts_dir = Path("workspace") / "prompts"
        self.logs_dir = Path("logs")

        # Создаем директорию logs/ если её нет
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # Загрузка промпта
        prompt_path = self.prompts_dir / "tester.md"
        if not prompt_path.exists():
            raise FileNotFoundError(f"Системный промпт не найден: {prompt_path}")
        with open(prompt_path, 'r', encoding='utf-8') as f:
            self.system_prompt = f.read()

        # Настройки для Ollama API
        self.ollama_url = "http://localhost:11434/api/generate"
        self.model_name = "qwen2.5-coder:3b"

    def run(self):
        """Основной метод выполнения задачи агентом."""
        code = self._read_project_code()

        if not code.strip():
            return {"status": "failure", "message": "В проекте нет файлов .py для анализа."}

        test_code = self._generate_tests(code)
        status = self._write_test_files(test_code)

        # Возвращаем только статус и краткое сообщение
        if status == "success":
            return {"status": "success", "message": "Юнит-тесты успешно сгенерированы."}
        else:
            return {"status": "failure", "message": "Возникли ошибки при генерации тестов."}

    def _log(self, message):
        """Логирование операций записи."""
        log_file = self.logs_dir / "tester_agent.log"
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(message + "\n")
        except Exception as e:
            print(f"Ошибка записи лога: {e}")

    def _read_project_code(self):
        """Читает все .py файлы из папки проекта и объединяет их в одну строку."""
        code_parts = []
        if not self.project_dir.exists():
            return ""

        # Используем rglob для поиска файлов во всех подпапках (src/, и т.д.)
        for py_file in self.project_dir.rglob('*.py'):
            # Пропускаем папку tests и её содержимое, чтобы не анализировать тесты как код проекта
            if 'tests' in str(py_file.parent):
                continue
            try:
                content = py_file.read_text(encoding='utf-8')
                code_parts.append(f"### ФАЙЛ: {py_file.relative_to(self.project_dir)} ###\n{content}")
            except Exception as e:
                self._log(f"Ошибка чтения файла {py_file}: {e}")
                print(f"Ошибка чтения файла {py_file}: {e}")

        return "\n\n".join(code_parts)

    def _generate_tests(self, code):
        """Отправляет код в Ollama для генерации тестов."""
        user_message = f"Вот исходный код проекта:\n{code}"
        payload = {
            "model": self.model_name,
            "prompt": self.system_prompt + "\n\n" + user_message,
            "stream": False
        }

        try:
            response = requests.post(self.ollama_url, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            return data.get('response', '')
        except requests.exceptions.RequestException as e:
            error_msg = f"Ошибка при запросе к Ollama API: {e}"
            self._log(error_msg)
            print(error_msg)
            return ""  # Возвращаем пустую строку для обработки в _write_test_files

    def _write_test_files(self, generated_code):
        """
        Записывает сгенерированный код тестов в файлы внутри папки tests/.
        """
        success = True

        if not generated_code:
            self._log("Ошибка: Не получено никакого кода от LLM.")
            return "failure"

        # Создаем директорию tests/ внутри папки проекта, если её нет
        try:
            self.tests_dir.mkdir(exist_ok=True)
            self._log(f"Успешно создана/проверена директория для тестов: {self.tests_dir}")
        except Exception as e:
            self._log(f"Ошибка создания директории tests/: {e}")
            return "failure"

        # Логика разделения на файлы по маркеру остается прежней
        blocks = generated_code.split('### FILE:')

        if len(blocks) == 1 and '### FILE:' not in generated_code:
            # Если маркеров нет, записываем всё в один файл по умолчанию
            default_path = self.tests_dir / "test_generated.py"
            try:
                default_path.write_text(generated_code.strip(), encoding='utf-8')
                self._log(f"Успешно записан файл (дефолтный): {default_path}")
            except Exception as e:
                self._log(f"Ошибка записи дефолтного файла: {e}")
                success = False
        else:
            # Если маркеры есть, обрабатываем каждый блок как отдельный файл
            for block in blocks[1:]:
                parts = block.strip().split('\n', 1)
                if len(parts) == 2:
                    filename, file_content = parts
                    filepath = self.tests_dir / filename.strip()
                    try:
                        filepath.write_text(file_content.strip(), encoding='utf-8')
                        self._log(f"Успешно записан файл: {filepath}")
                    except Exception as e:
                        self._log(f"Ошибка записи файла {filepath}: {e}")
                        success = False

        return "success" if success else "failure"