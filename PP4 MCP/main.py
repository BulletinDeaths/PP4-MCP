import os
import sys
import logging
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from core.orchestrator import Orchestrator

stdout_handler = logging.StreamHandler(sys.stdout)

# Создаем форматтер, который будет выводить только само сообщение без лишней информации.
formatter = logging.Formatter('%(message)s')
stdout_handler.setFormatter(formatter)

# Находим логгеры, которые мы хотим перенастроить.
root_logger = logging.getLogger()
analyst_logger = logging.getLogger('agents.analyst')

# Добавляем наш новый обработчик к этим логгерам.
root_logger.addHandler(stdout_handler)
analyst_logger.addHandler(stdout_handler)

# Устанавливаем уровень логгирования на INFO, чтобы видеть эти сообщения.
root_logger.setLevel(logging.INFO)
analyst_logger.setLevel(logging.INFO)

# отключаем propagation сообщений от дочерних логгеров к родительским, чтобы избежать дублирования строк в консоли.
analyst_logger.propagate = False


def main():
    orchestrator = Orchestrator(
        agents_dir="agents",
        workspace_dir="workspace",
        logs_dir="logs"
    )

    print("ИИ-Фабрика запущена. Введите сообщение для агента (введите 'exit' for exit).")
    development_in_progress = False
    last_project_name = ""

    while True:
        user_input = input("Вы: ")

        if user_input.lower() == 'exit':
            print("Завершение работы...")
            break

        response = orchestrator.process_user_input(user_input)

        # --- НОВАЯ ЛОГИКА ПРОВЕРКИ ---
        if "Запущена задача на разработку" in response:
            development_in_progress = True
            print(response + " Я проверю готовность проекта автоматически.")

        # Если задача в процессе, проверяем папку projects/
        if development_in_progress:
            projects_path = Path("workspace") / "projects"
            if projects_path.exists():
                # Находим новую папку проекта
                project_folders = [d for d in projects_path.iterdir() if d.is_dir()]
                if project_folders:
                    # Берем последнюю созданную папку (предполагаем, что это наша)
                    current_project_name = project_folders[-1].name
                    if current_project_name != last_project_name:
                        print(f"\nАгент: Обнаружен новый проект '{current_project_name}'!")
                        last_project_name = current_project_name
                        development_in_progress = False  # Задача выполнена

                        # Теперь здесь можно было бы автоматически запустить тестера,
                        # но ваш текущий Orchestrator этого не ожидает.
                        # Поэтому просто сообщаем пользователю.
                        print(
                            f"Агент: Проект '{current_project_name}' готов. Вы можете проверить его в папке 'workspace/projects'.")

        # Если никакой специальной проверки не нужно, просто печатаем ответ
        elif not development_in_progress:
            print(f"Агент: {response}")


if __name__ == "__main__":
    main()