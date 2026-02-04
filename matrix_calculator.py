from datetime import datetime
from typing import Dict, List, Tuple
import math

class MatrixCalculator:
    def __init__(self):
        self.zodiac_signs = {
            (3, 21): "Овен", (4, 20): "Телец", (5, 21): "Близнецы",
            (6, 22): "Рак", (7, 23): "Лев", (8, 23): "Дева",
            (9, 23): "Весы", (10, 23): "Скорпион", (11, 22): "Стрелец",
            (12, 22): "Козерог", (1, 20): "Водолей", (2, 19): "Рыбы"
        }
    
    def string_sum(self, number: int) -> int:
        """Сумма цифр числа"""
        return sum(int(digit) for digit in str(number))
    
    def split_int(self, value: str) -> List[int]:
        """Разделение числа на цифры"""
        return [int(digit) for digit in str(value) if digit.isdigit()]
    
    def calculate_matrix(self, birth_date: str, gender: str) -> Dict:
        """Основной расчет матрицы"""
        try:
            date_obj = datetime.strptime(birth_date, "%d.%m.%Y")
        except:
            date_obj = datetime.strptime(birth_date, "%Y-%m-%d")
        
        formatted_date = date_obj.strftime("%d.%m.%Y")
        year = date_obj.year
        
        # Разбиваем дату на цифры
        numbers = [int(digit) for digit in formatted_date.replace(".", "")]
        
        # Первое число - сумма всех цифр даты
        first = sum(numbers)
        
        # Второе число - сумма цифр первого числа
        second = self.string_sum(first)
        
        # Третье число
        if year >= 2000:
            third = first - 19
        else:
            first_digit = numbers[0] if numbers[0] != 0 else numbers[1]
            third = first - (first_digit * 2)
        
        # Четвертое число - сумма цифр третьего
        fourth = self.string_sum(third)
        
        # Формируем дополнительный ряд
        if year >= 2000:
            additional = [first, second, 19, third, fourth]
            full_array = numbers + self.split_int(first) + self.split_int(second) + [1, 9] + self.split_int(third) + self.split_int(fourth)
        else:
            additional = [first, second, third, fourth]
            full_array = numbers + self.split_int(first) + self.split_int(second) + self.split_int(third) + self.split_int(fourth)
        
        # Строим матрицу 3x3
        matrix_3x3 = {}
        for i in range(1, 10):
            matrix_3x3[i] = [str(x) for x in full_array if x == i]
        
        # Добавляем дополнительную 9 для года >= 2020
        if year >= 2020 and '9' in matrix_3x3:
            matrix_3x3[9].append('9')
        
        return {
            'date': birth_date,
            'year': year,
            'numbers': numbers,
            'additional': additional,
            'first': first,
            'second': second,
            'third': third,
            'fourth': fourth,
            'full_array': full_array,
            'matrix_3x3': matrix_3x3,
            'zodiac': self.get_zodiac_sign(date_obj.month, date_obj.day),
            'gender': gender
        }
    
    def get_zodiac_sign(self, month: int, day: int) -> str:
        """Определение знака зодиака"""
        for (m, d), sign in sorted(self.zodiac_signs.items()):
            if (month == m and day >= d) or (month == m + 1 and day < d):
                return sign
        return "Козерог"
    
    def format_matrix_display(self, matrix_data: Dict) -> str:
        """Форматирование матрицы для отображения"""
        matrix = matrix_data['matrix_3x3']
        lines = []
        
        # Первая строка
        lines.append("┌─────────┬─────────┬─────────┐")
        lines.append(f"│   1     │    4    │    7    │")
        lines.append("├─────────┼─────────┼─────────┤")
        line1 = "│"
        for num in [1, 4, 7]:
            cells = matrix.get(num, [])
            display = ' '.join(cells) if cells else '—'
            line1 += f" {display:^7} │"
        lines.append(line1)
        lines.append("├─────────┼─────────┼─────────┤")
        
        # Вторая строка
        lines.append(f"│   2     │    5    │    8    │")
        lines.append("├─────────┼─────────┼─────────┤")
        line2 = "│"
        for num in [2, 5, 8]:
            cells = matrix.get(num, [])
            display = ' '.join(cells) if cells else '—'
            line2 += f" {display:^7} │"
        lines.append(line2)
        lines.append("├─────────┼─────────┼─────────┤")
        
        # Третья строка
        lines.append(f"│   3     │    6    │    9    │")
        lines.append("├─────────┼─────────┼─────────┤")
        line3 = "│"
        for num in [3, 6, 9]:
            cells = matrix.get(num, [])
            display = ' '.join(cells) if cells else '—'
            if num == 9 and matrix_data['year'] >= 2020:
                display = display + ' 9' if display != '—' else '9'
            line3 += f" {display:^7} │"
        lines.append(line3)
        lines.append("└─────────┴─────────┴─────────┘")
        
        return "\n".join(lines)
