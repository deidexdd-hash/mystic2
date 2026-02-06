#!/usr/bin/env python3
"""
Тестовый скрипт для проверки корректности расчета матрицы
"""

from matrix_calculator import MatrixCalculator

def test_matrix():
    calc = MatrixCalculator()
    
    print("=" * 50)
    print("ТЕСТИРОВАНИЕ РАСЧЕТА МАТРИЦЫ")
    print("=" * 50)
    
    # Тест 1: Дата до 2000 года
    print("\n1. Тест для даты до 2000 года: 15.05.1992")
    matrix1 = calc.calculate_matrix("15.05.1992")
    if matrix1:
        print(f"Дополнительные числа: {matrix1['additional']}")
        print(f"Полный массив: {matrix1['full_array']}")
        print("\nМатрица:")
        print(calc.format_matrix_display(matrix1))
    
    # Тест 2: Дата после 2000 года
    print("\n2. Тест для даты после 2000 года: 10.03.2005")
    matrix2 = calc.calculate_matrix("10.03.2005")
    if matrix2:
        print(f"Дополнительные числа: {matrix2['additional']}")
        print(f"Полный массив: {matrix2['full_array']}")
        print("\nМатрица:")
        print(calc.format_matrix_display(matrix2))
    
    # Тест 3: Дата после 2020 года (должна быть дополнительная 9)
    print("\n3. Тест для даты после 2020 года: 25.12.2021")
    matrix3 = calc.calculate_matrix("25.12.2021")
    if matrix3:
        print(f"Дополнительные числа: {matrix3['additional']}")
        print(f"Полный массив: {matrix3['full_array']}")
        print(f"Должна быть дополнительная 9 в массиве!")
        print("\nМатрица:")
        print(calc.format_matrix_display(matrix3))
        
    # Тест интерпретаций
    print("\n4. Тест интерпретаций для женщины (15.05.1992)")
    if matrix1:
        interpretations = calc.get_interpretations(matrix1, "женский")
        print(interpretations[:500] + "...\n(показаны первые 500 символов)")

if __name__ == "__main__":
    test_matrix()
