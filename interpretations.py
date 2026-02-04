# Сокращенная версия - полный файл будет слишком большим
# Здесь нужно импортировать полные данные из values.ts

MATRIX_INTERPRETATIONS = {
    # Ваши данные из values.ts - преобразованные в Python словарь
    # Пример:
    "1": {
        "women": "Женщины: деспот. При рождении милосердные...",
        "men": "Мужчины: крайне любит отыгрываться на других людях..."
    },
    "11": {
        "women": "Женщины: семейная женщина...",
        "men": "Мужчины: много страхов..."
    }
    # ... остальные значения
}

TASKS = {
    "1": "Я, эго, амбиции, активность...",
    "2": "Девиз: «Давайте жить дружно!»...",
    # ... остальные значения
}

class Interpretations:
    def __init__(self):
        self.matrix_data = MATRIX_INTERPRETATIONS
        self.tasks_data = TASKS
    
    def get_matrix_value(self, number: int, count: int, gender: str) -> str:
        """Получение интерпретации для числа матрицы"""
        key = str(number)
        if count == 0:
            key = f"{number}0"
        elif count > 5:
            # Для более 5 берем все кроме первых 5
            key = str(number) * (count - 5)
        
        if key in self.matrix_data:
            data = self.matrix_data[key]
            if isinstance(data, dict):
                return data.get(gender.lower(), data.get('women', ''))
            return data
        return ""
    
    def get_task_interpretation(self, task_number: str) -> str:
        """Получение интерпретации задачи"""
        return self.tasks_data.get(task_number, "")
    
    def generate_full_interpretation(self, matrix_data: dict) -> str:
        """Генерация полной интерпретации для пользователя"""
        gender = matrix_data['gender'].lower()
        second_num = str(matrix_data['second'])
        fourth_num = str(matrix_data['fourth'])
        
        result = []
        result.append("🔮 *НУМЕРОЛОГИЧЕСКАЯ МАТРИЦА* 🔮\n")
        result.append(f"📅 Дата рождения: {matrix_data['date']}")
        result.append(f"♈ Знак зодиака: {matrix_data['zodiac']}")
        result.append(f"⚧ Пол: {matrix_data['gender']}\n")
        
        # Дополнительные числа
        result.append(f"🔢 Дополнительные числа: {'.'.join(map(str, matrix_data['additional']))}\n")
        
        # Личная задача Души
        result.append("🌟 *Личная задача Души* 🌟")
        result.append(self.get_task_interpretation(second_num))
        result.append("")
        
        # Родовая задача
        result.append("👨‍👩‍👧‍👦 *Родовая задача. ЧРП* 👨‍👩‍👧‍👦")
        result.append(self.get_task_interpretation(fourth_num))
        result.append("")
        
        # Значения цифр матрицы
        result.append("📊 *ЗНАЧЕНИЯ ЦИФР В МАТРИЦЕ* 📊\n")
        
        for i in range(1, 10):
            count = len([x for x in matrix_data['full_array'] if x == i])
            interpretation = self.get_matrix_value(i, count, gender)
            
            if interpretation:
                result.append(f"🔸 *Цифра {i}*")
                result.append(f"Количество: {count}")
                result.append(f"Значение: {interpretation[:200]}...")
                result.append("")
        
        return "\n".join(result)
