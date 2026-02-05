import logging
from interpretations import Interpretations

log = logging.getLogger(__name__)

class MatrixCalculator:
    def __init__(self):
        self.interp = Interpretations()
    
    def calculate_matrix(self, birth_date_str: str):
        """Полный расчет нумерологической матрицы по алгоритму из App.tsx"""
        try:
            # Парсинг даты
            parts = birth_date_str.split('.')
            if len(parts) != 3:
                return None
            
            day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
            
            # Разбиваем дату на цифры (убираем точки)
            nums = [int(d) for d in birth_date_str.replace('.', '')]
            
            # Первое число - сумма всех цифр даты
            first = sum(nums)
            
            # Второе число - сумма цифр первого числа
            second = sum(int(d) for d in str(first))
            
            # Третье число зависит от года рождения
            if year >= 2000:
                # Для людей родившихся после 2000 года
                third = first + 19
                additional = [first, second, 19, third]
            else:
                # Для людей до 2000 года
                first_digit = next(d for d in str(day) if d != '0')
                third = first - (int(first_digit) * 2)
                additional = [first, second, third]
            
            # Четвертое число - сумма цифр третьего числа
            fourth = sum(int(d) for d in str(third))
            additional.append(fourth)
            
            # Полный массив: цифры даты + доп. числа (разбитые на цифры)
            full_array = nums.copy()
            for num in additional:
                full_array.extend([int(d) for d in str(num)])
            
            # Особый случай: для рожденных >= 2020, добавляем дополнительную 9
            if year >= 2020:
                full_array.append(9)
            
            # Заполнение ячеек 1-9
            matrix = {}
            for i in range(1, 10):
                count = full_array.count(i)
                if count > 0:
                    # Сохраняем числа через пробел как в App.tsx
                    matrix[str(i)] = ' '.join([str(i)] * count)
                else:
                    matrix[str(i)] = "—"
            
            matrix["additional"] = additional
            matrix["date"] = birth_date_str
            matrix["year"] = year
            matrix["full_array"] = full_array
            
            return matrix
            
        except Exception as e:
            log.error(f"Ошибка в расчете матрицы: {e}")
            return None

    def format_matrix_display(self, matrix_data: dict) -> str:
        """Отрисовка таблицы с использованием моноширинных рамок"""
        m = {str(i): matrix_data.get(str(i), "—") for i in range(1, 10)}

        header = "┏━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┓"
        row1   = f"┃{m['1']:^9}┃{m['4']:^9}┃{m['7']:^9}┃"
        sep    = "┣━━━━━━━━━╋━━━━━━━━━╋━━━━━━━━━┫"
        row2   = f"┃{m['2']:^9}┃{m['5']:^9}┃{m['8']:^9}┃"
        row3   = f"┃{m['3']:^9}┃{m['6']:^9}┃{m['9']:^9}┃"
        footer = "┗━━━━━━━━━┻━━━━━━━━━┻━━━━━━━━━┛"

        return f"{header}\n{row1}\n{sep}\n{row2}\n{sep}\n{row3}\n{footer}"
    
    def get_interpretations(self, matrix_data: dict, gender: str) -> str:
        """Получение интерпретаций для матрицы с учетом пола"""
        try:
            result = []
            
            # Дополнительные числа
            additional = matrix_data.get("additional", [])
            if len(additional) >= 4:
                second = str(additional[1])
                fourth = str(additional[3])
                
                result.append("🎯 *ЛИЧНАЯ ЗАДАЧА ДУШИ*")
                task_text = self.interp.tasks_data.get(second, "Нет данных")
                result.append(task_text)
                result.append("")
                
                result.append("👪 *РОДОВАЯ ЗАДАЧА (ЧРП)*")
                task_text = self.interp.tasks_data.get(fourth, "Нет данных")
                result.append(task_text)
                result.append("")
            
            result.append("📊 *ЗНАЧЕНИЯ МАТРИЦЫ*\n")
            
            # Интерпретации для каждой цифры
            for num in range(1, 10):
                cell_value = matrix_data.get(str(num), "—")
                
                # Пропускаем пустые ячейки
                if cell_value == "—":
                    continue
                
                # Определяем ключ для интерпретации (количество цифр)
                count = len(cell_value.replace(' ', ''))
                
                # Формируем ключ
                if num in [1, 2, 3, 4, 6, 7, 8, 9]:
                    # Для этих цифр есть разные интерпретации
                    if count == 0:
                        key = f"{num}0"
                    else:
                        key = str(num) * count
                else:
                    key = str(num) * count if count > 0 else f"{num}0"
                
                # Получаем интерпретацию
                interpretation = self.interp.matrix_data.get(key, "")
                
                if interpretation:
                    result.append(f"*Цифра {num}* ({cell_value}):")
                    
                    # Если интерпретация зависит от пола (словарь)
                    if isinstance(interpretation, dict):
                        if gender == "женский":
                            text = interpretation.get("women", "")
                        else:  # мужской
                            text = interpretation.get("men", "")
                        
                        if text:
                            result.append(text)
                    else:
                        # Обычная интерпретация (строка)
                        result.append(interpretation)
                    
                    result.append("")
            
            return "\n".join(result)
            
        except Exception as e:
            log.error(f"Ошибка в получении интерпретаций: {e}")
            return "❌ Не удалось получить интерпретации"
