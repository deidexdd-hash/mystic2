import logging

log = logging.getLogger(__name__)

class MatrixCalculator:
    def calculate_matrix(self, birth_date_str: str):
        """Полный расчет нумерологической матрицы"""
        try:
            # Убираем точки из даты
            nums = [int(d) for d in birth_date_str if d.isdigit()]
            if not nums: return None
            
            # Основные расчеты
            sum1 = sum(nums)
            sum2 = sum(int(d) for d in str(sum1))
            
            first_digit = next(d for d in birth_date_str if d.isdigit() and d != '0')
            sum3 = abs(sum1 - 2 * int(first_digit))
            sum4 = sum(int(d) for d in str(sum3))
            
            additional = [sum1, sum2, sum3, sum4]
            full_array = nums + additional
            
            # Заполнение ячеек 1-9
            matrix = {}
            for i in range(1, 10):
                count = full_array.count(i)
                matrix[str(i)] = str(i) * count if count > 0 else "-"
            
            matrix["additional"] = additional
            matrix["date"] = birth_date_str
            return matrix
        except Exception as e:
            log.error(f"Ошибка в расчете матрицы: {e}")
            return None

    def format_matrix_display(self, matrix_data: dict) -> str:
        """Отрисовка таблицы с использованием моноширинных рамок"""
        # Безопасно извлекаем значения
        m = {str(i): matrix_data.get(str(i), "-") for i in range(1, 10)}

        # Используем Unicode-символы рамок
        # :^7 означает центрирование текста в колонке шириной 7 символов
        header = "┏━━━━━━━┳━━━━━━━┳━━━━━━━┓"
        row1   = f"┃{m['1']:^7}┃{m['4']:^7}┃{m['7']:^7}┃"
        sep    = "┣━━━━━━━╋━━━━━━━╋━━━━━━━┫"
        row2   = f"┃{m['2']:^7}┃{m['5']:^7}┃{m['8']:^7}┃"
        row3   = f"┃{m['3']:^7}┃{m['6']:^7}┃{m['9']:^7}┃"
        footer = "┗━━━━━━━┻━━━━━━━┻━━━━━━━┛"

        return f"{header}\n{row1}\n{sep}\n{row2}\n{sep}\n{row3}\n{footer}"
