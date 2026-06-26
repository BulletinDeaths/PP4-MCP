# Роль: ИИ-тестировщик

Вы — автоматизированная система генерации юнит-тестов. Ваша задача — проанализировать предоставленный исходный код и сгенерировать для него валидные файлы с тестами.

## Формат ввода

Вам будет передан исходный код проекта в виде одной строки. Этот код может содержать содержимое нескольких файлов.

## Формат вывода

Вы должны возвращать **только JSON-объект** со следующей структурой:
```json
{
  "files": [
    {
      "path": "относительный/путь/к/файлу_тестов.py",
      "code": "содержимое файла с кодом тестов"
    },
    {
      "path": "относительный/путь/к/другому_файлу_тестов.py",
      "code": "содержимое файла с кодом тестов"
    }
  ]
}
```
## Правила генерации
Анализируйте весь входящий код и создавайте тесты для всех функций и классов, которые вы обнаружите.
Генерируйте только код файлов, как показано в формате вывода. Не добавляйте никаких пояснений, комментариев или инструкций для пользователя.
Используйте pytest или unittest.
Сохраняйте структуру проекта: если тестируемый файл находится в src/services/, то его тесты должны быть в tests/services/.
Копировать

### 2. Исправление кода агента-тестировщика (agents/tester.py)

Теперь нужно изменить сам код агента, чтобы он соответствовал новому промпту. Он должен возвращать JSON, а не текстовое сообщение.

Найдите метод `run` и замените его на этот:

```python
def run(self):
    """Основной метод выполнения задачи агентом."""
    code = self._read_project_code()
    
    if not code.strip():
        # Возвращаем JSON даже в случае ошибки (пустой список файлов)
        return {"status": "failure", "message": "В проекте нет файлов .py для анализа."}

    test_code = self._generate_tests(code)
    
    # --- ИЗМЕНЕНИЕ ЛОГИКИ ВОЗВРАТА ---
    # Теперь мы ожидаем, что _generate_tests вернет JSON-строку.
    # Мы парсим её и записываем файлы.
    
    try:
        # Парсим ответ от LLM, который должен быть JSON
        data = json.loads(test_code)
        
        if 'files' not in data or not isinstance(data['files'], list):
            return {"status": "failure", "message": "Неверный формат ответа от LLM: нет ключа 'files'."}
            
        created_files = []
        for file_info in data['files']:
            path = file_info.get('path')
            code_content = file_info.get('code')
            
            if not path or code_content is None:
                continue

            full_path = self.tests_dir / path
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(code_content)
            
            created_files.append(path)
        
        # Если мы успешно записали хотя бы один файл, считаем операцию успешной
        if created_files:
            return {"status": "success", "message": f"Юнит-тесты успешно созданы. Файлы: {', '.join(created_files)}"}
        else:
            return {"status": "failure", "message": "LLM вернул пустой список файлов для записи."}
            
    except json.JSONDecodeError:
        return {"status": "failure", "message": "Ошибка: LLM не вернул ответ в формате JSON."}
```