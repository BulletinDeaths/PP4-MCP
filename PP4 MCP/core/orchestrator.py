import os
import json
import subprocess
import requests
from typing import Dict, Optional, List


class Orchestrator:
    """
    Ядро MCP сервера. Управляет запуском агентов, хранит общую память и взаимодействует с LLM.
    """

    def __init__(self, agents_dir: str, workspace_dir: str, logs_dir: str):
        """
        Инициализация
        """
        self.agents_dir = agents_dir
        self.workspace_dir = workspace_dir
        self.logs_dir = logs_dir

        # Создаем директорию логов, если её нет
        os.makedirs(self.logs_dir, exist_ok=True)

        # Общая память агентов (словарь)
        self.shared_memory: Dict[str, str] = {}

        # Загрузка конфигов из workspace
        self.load_workspace()

        # Поиск доступных агентов в папке agents (для динамической загрузки)
        self.available_agents = self._find_available_agents()

        if not self.available_agents:
            print("Предупреждение: В папке 'agents' не найдено ни одного файла агента.")
            self.available_agents = ['test_agent']  # Заглушка для теста

    def _find_available_agents(self) -> list:
        """Вспомогательный метод для поиска файлов агентов в директории."""
        agents = []
        for file in os.listdir(self.agents_dir):
            if file.endswith('.py') and file != '__init__.py':
                agents.append(file[:-3])
        return agents

    def load_workspace(self):
        """Загрузка данных из рабочей директории"""
        config_path = os.path.join(self.workspace_dir, 'config.json')
        if os.path.exists(config_path) and os.path.getsize(config_path) > 0:
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    self.shared_memory.update(json.load(f))
                print(f"Загружено {len(self.shared_memory)} ключей из конфига.")
            except json.JSONDecodeError:
                print(f"Внимание: файл {config_path} повреждён или содержит некорректный JSON. Пропускаю загрузку.")
        else:
            print(f"Файл {config_path} не найден или пустой. Используется память по умолчанию.")

    def process_user_input(self, user_input: str) -> str:
        """
        Принимает ввод от пользователя и обрабатывает его.
        Поддерживает команду для смены активного агента.
        """
        # --- КОМАНДА ДЛЯ СМЕНЫ АГЕНТА ---
        # Если пользователь вводит "use <имя_агента>", меняем активного агента
        if user_input.lower().startswith("use "):
            agent_name = user_input[4:].strip()  # Убираем "use " и пробелы

            if agent_name in self.available_agents:
                self.active_agent_name = agent_name
                return f"Агент успешно переключен на '{agent_name}'."
            else:
                return f"Ошибка: Агент '{agent_name}' не найден. Доступные агенты: {', '.join(self.available_agents)}"

        # Если пользователь просто ввел имя доступного агента, тоже переключаемся
        elif user_input.lower() in self.available_agents:
            self.active_agent_name = user_input.lower()
            return f"Агент успешно переключен на '{self.active_agent_name}'."

        # --- ОСНОВНАЯ ЛОГИКА ОБРАБОТКИ ---
        # Если не было команды смены агента, используем текущего
        agent_name = getattr(self, 'active_agent_name', self.available_agents[0])

        try:
            # Динамическая загрузка модуля активного агента
            agent_module = __import__(f"{self.agents_dir}.{agent_name}", fromlist=['Agent'])
            agent_instance = agent_module.Agent(orchestrator=self)

            # Передаем ввод агенту и получаем ответ
            response = agent_instance.handle_message(user_input)

            # Логируем взаимодействие
            self._log_interaction(user_input, response)

            return response

        except Exception as e:
            return f"Ошибка при обработке запроса агентом {agent_name}: {str(e)}"

    def _log_interaction(self, user_input: str, agent_response: str):
        """Записывает лог взаимодействия в файл."""
        log_file = os.path.join(self.logs_dir, 'server.log')
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"[User] {user_input}\n")
            f.write(f"[Agent] {agent_response}\n")
            f.write("-" * 20 + "\n")

    def call_ollama_api(self, prompt: str, model: str = "qwen2.5-coder:3b") -> Optional[str]:
        try:
            url = "http://localhost:11434/api/generate"
            payload = {"model": model, "prompt": prompt, "stream": False}
            response = requests.post(url, json=payload)
            response.raise_for_status()

            data = response.json()
            return data.get('response')

        except requests.exceptions.RequestException as e:
            print(f"Ошибка при запросе к Ollama API: {e}")
            return None

    def call_gigachat_api(
        self,
        messages: List[Dict[str, str]],
        model: str = "GigaChat",
        temperature: float = 0.7,
        max_tokens: int = 1024
    ) -> Optional[str]:
        """
        Вызов GigaChat API (Сбер).
        Требуется OAuth-токен в config.json: "gigachat_token".
        """
        token = self.shared_memory.get('gigachat_token')
        if not token:
            print("Ошибка: gigachat_token не задан в config.json")
            return None

        url = self.shared_memory.get(
            'gigachat_api_url',
            'https://gigachat.devices.sberbank.ru/api/v1/chat/completions'
        )

        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()

            data = response.json()
            return data['choices'][0]['message']['content']

        except requests.exceptions.RequestException as e:
            print(f"Ошибка при запросе к GigaChat API: {e}")
            return None
        except (KeyError, IndexError) as e:
            print(f"Ошибка парсинга ответа GigaChat: {e}")
            return None

    def ask_llm(self, prompt: str, provider: str = "ollama") -> Optional[str]:
        """
        Универсальный метод вызова LLM через указанный провайдер.
        provider: "ollama" | "gigachat"
        """
        if provider == "gigachat":
            messages = [{"role": "user", "content": prompt}]
            return self.call_gigachat_api(messages)
        else:
            return self.call_ollama_api(prompt)

def fake_llm(prompt):
    return f"[FakeLLM Echo] Вы сказали: '{prompt}'"