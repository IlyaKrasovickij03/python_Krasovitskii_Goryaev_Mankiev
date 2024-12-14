from collections import OrderedDict
import functools


def cache_decorator(cache_depth=3):
    def decorator(func):
        cache = OrderedDict()

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))

            if key in cache:
                # Перемещаем использованный ключ в конец, чтобы сохранить порядок по времени использования
                cache.move_to_end(key)
                print(f'Get the value from cache')
                return cache[key]

            # Ограничение размера кэша
            if len(cache) >= cache_depth:
                oldest_key, oldest_value = cache.popitem(last=False)
                print(f'Remove the oldest element in cache: func = {func.__name__}{oldest_key[0]}, value = {oldest_value}')

            # Вызов функции и кэширование результата
            result = func(*args, **kwargs)
            print('Add value to cache')
            cache[key] = result

            return result

        return wrapper

    return decorator


@cache_decorator(2)
def multiplication(a, b):
    print(f'Execution of function multiplication({a}, {b})')
    return a * b


@cache_decorator(3)
def subtraction(a, b):
    print(f'Execution of function subtraction({a}, {b})')
    return a - b


if __name__ == '__main__':
    print(multiplication(2, 2)) # Результат добавится в кэш
    print()
    print(multiplication(3, 3)) # Результат добавится в кэш
    print()
    print(multiplication(2, 2)) # Результат будет взят из кэша
    print()
    print(multiplication(4, 4)) # Кэш переполнится, будет удалён старейший элемент
    print('//////////////////////////////////////////////////////////////////')
    print(subtraction(5,1))  # Результат добавится в кэш
    print()
    print(subtraction(4, 2)) # Результат добавится в кэш
    print()
    print(subtraction(3, 1)) # Результат добавится в кэш
    print()
    print(subtraction(5, 1)) # Результат будет взят из кэша
    print()
    print(subtraction(100, 90)) # Кэш переполнится, будет удалён старейший элемент
    print()