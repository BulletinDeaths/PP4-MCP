import os
import json
import logging
import re
import json5

logger = logging.getLogger(__name__)


class DeveloperAgent:
    def __init__(self, orchestrator, projects_dir):
        self.orchestrator = orchestrator
        self.prompt_path = os.path.join("workspace", "prompts", "developer.md")
        self.projects_dir = projects_dir

    def handle_message(self) -> str:
        """Читает ТЗ из памяти, генерирует код через LLM и записывает файлы в подпапку проекта."""
        logger.info("Разработчик ищет ТЗ в общей памяти...")

        raw_analyst_result = self.orchestrator.shared_memory.get('analyst_result_raw')

        if not raw_analyst_result:
            return "Ошибка: ТЗ от агента-аналитика отсутствует. Сначала сформулируйте запрос на разработку."

        project_name = self._extract_project_name(raw_analyst_result)
        project_dir = os.path.join(self.projects_dir, project_name)
        os.makedirs(project_dir, exist_ok=True)
        logger.info(f"Директория проекта: {project_dir}")

        try:
            with open(self.prompt_path, 'r', encoding='utf-8') as f:
                developer_prompt = f.read()
        except FileNotFoundError:
            return "Ошибка: файл промпта разработчика не найден."

        full_prompt = f"{developer_prompt}\n\nВот ТЗ:\n{raw_analyst_result}"
        logger.info("Отправляю ТЗ разработчику для генерации кода...")

        llm_response = self.orchestrator.ask_llm(full_prompt)

        if not llm_response or not llm_response.strip():
            return "Ошибка: LLM не вернул ответ при генерации кода."

        files_list = self._extract_files(llm_response)

        if not files_list:
            logger.warning("LLM не вернул валидный JSON. Записываю сырой ответ как README.")
            readme_path = os.path.join(project_dir, "output.md")
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(llm_response)
            # Даже при ошибке парсинга, возвращаем путь к созданной папке проекта.
            return project_dir

        created_files = []

        for file_info in files_list:
            path = file_info.get('path')
            code = file_info.get('code')

            if not path or code is None:
                logger.warning(f"Пропуск файла: {file_info}")
                continue

            full_path = os.path.join(project_dir, path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(code)

            created_files.append(path)
            logger.info(f"Создан файл: {full_path}")

        return project_dir

    def _extract_project_name(self, tz_json: str) -> str:
        """Извлекает project_name из JSON ТЗ."""
        try:
            cleaned = tz_json.strip()
            if "```json" in cleaned:
                start = cleaned.find("```json") + len("```json")
                end = cleaned.rfind("```")
                cleaned = cleaned[start:end].strip()
            data = json5.loads(cleaned)
            if isinstance(data, dict) and 'project_name' in data:
                name = data['project_name'].strip()
                name = re.sub(r'[^a-zA-Z0-9_]', '', name)
                return name if name else 'UntitledProject'
        except Exception:
            pass
        return 'UntitledProject'

    def _extract_files(self, llm_response: str) -> list:
        """Извлекает список файлов из ответа LLM (JSON или markdown)."""
        cleaned = llm_response.strip()
        if "```json" in cleaned and "```" in cleaned:
            start = cleaned.find("```json") + len("```json")
            end = cleaned.rfind("```")
            cleaned = cleaned[start:end].strip()

        cleaned = self._fix_triple_quotes(cleaned)

        try:
            generated = json5.loads(cleaned)
            if isinstance(generated, dict) and 'files' in generated:
                return generated['files']
            if isinstance(generated, list):
                return generated
        except Exception:
            pass

        return self._parse_markdown_blocks(llm_response)

    def _fix_triple_quotes(self, text: str) -> str:
        """Заменяет тройные кавычки LLM на обычные экранированные строки."""
        import re

        def replace_triple(m):
            content = m.group(1)
            content = content.replace('\\', '\\\\')
            content = content.replace('"', '\\"')
            content = content.replace('\n', '\\n')
            content = content.replace('\t', '\\t')
            return '"' + content + '"'

        result = re.sub(r'"""(.*?)"""', replace_triple, text, flags=re.DOTALL)
        result = re.sub(r"'''(.*?)'''", replace_triple, result, flags=re.DOTALL)
        return result

    def _parse_markdown_blocks(self, text: str) -> list:
        """Извлекает файлы из markdown-блоков кода и по комментариям с именами файлов."""
        files = []
        pattern = r'```(?:\w+)?\s*\n(.*?)```'
        blocks = re.findall(pattern, text, re.DOTALL)

        for block in blocks:
            sub_files = self._split_by_filename_comments(block)
            files.extend(sub_files)

        if not files and text.strip():
            files = self._split_by_filename_comments(text)

        return files

    def _split_by_filename_comments(self, code: str) -> list:
        """Разбивает код на файлы по комментариям вида # filename.py"""
        files = []
        parts = re.split(r'\n(?=\S[\w\-./]*\.\w+\s*$)', code.strip())

        if len(parts) <= 1:
            counter = 0
            for block in re.split(r'\n{3,}', code.strip()):
                block = block.strip()
                if not block:
                    continue
                lines = block.split('\n')
                first = lines[0].strip()
                if first.startswith('#') and not first.startswith('#!') and ('.' in first):
                    path = first.lstrip('#').strip()
                    code_content = '\n'.join(lines[1:]).strip()
                else:
                    counter += 1
                    ext = self._guess_extension(block)
                    path = f"generated_{counter}{ext}"
                    code_content = block

                if code_content:
                    files.append({'path': path, 'code': code_content})
            return files

        for part in parts:
            part = part.strip()
            if not part:
                continue
            lines = part.split('\n')
            first = lines[0].strip()

            if first.startswith('#') and not first.startswith('#!'):
                path = first.lstrip('#').strip()
                code_content = '\n'.join(lines[1:]).strip()
            else:
                ext = self._guess_extension(part)
                path = f"generated_{len(files) + 1}{ext}"
                code_content = part

            if code_content:
                files.append({'path': path, 'code': code_content})

        return files

    def _guess_extension(self, code: str) -> str:
        """Угадывает расширение файла по содержимому."""
        if 'def ' in code or 'import ' in code or 'class ' in code:
            return '.py'
        if '<html' in code.lower() or '<div' in code.lower():
            return '.html'
        if '{' in code and '}' in code and '"' in code:
            return '.json'
        return '.txt'
