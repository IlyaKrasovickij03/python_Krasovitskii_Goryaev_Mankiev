#
# Задание 1_figures.

#   Необходимо с помощью @properties исправить код из презентации так, чтобы принцип Барбары Лисков не нарушался.
#   Принцип подстановки Барбары Лисков (LSP) звучит так: если для любого объекта o1 типа S существует такой объект o2 типа T, что для всех
#   программ P, определённых в терминах Т, поведение Р не изменяется при подстановке o1 вместо o2, то S - подтип Т.

#   В нашем случае это означает, что методы для получения и установки ширины и высоты должны работать одинаково для обоих классов.
#   Если мы можем заменить объект Rectangle объектом Square и программа продолжит работать корректно, то принцип LSP соблюдается.


class Shape:
    name = 'Фигура'

    def __init__(self, x, y):
        self.__x = x
        self.__y = y

    def __repr__(self):
        return f"{self.name} находится в точке ({self.__x}, {self.__y})"


class Rectangle(Shape):
    name = 'Прямоугольник'

    def __init__(self, width, height, x=0, y=0):
        super().__init__(x, y)
        self._width = width
        self._height = height

    @property
    def width(self):
        return self._width

    @width.setter
    def width(self, value):
        self._width = value

    @property
    def height(self):
        return self._height

    @height.setter
    def height(self, value):
        self._height = value

    def __repr__(self):
        return (f"{Shape.__repr__(self)}, ширина: {self.width} и высота:{self.height}")


class Square(Rectangle):
    name = 'Квадрат'

    def __init__(self, side, x=0, y=0):
        super().__init__(side, side, x, y)

    @property
    def width(self):
        return self._width

    @width.setter
    def width(self, value):
        self._width = self._height = value

    @property
    def height(self):
        return self._height

    @height.setter
    def height(self, value):
        self._width = self._height = value

    def __repr__(self):
        return (f"{Shape.__repr__(self)}, со стороной {self.width}")

# Тесты

#  Для начала зададим параметры прямоугольника
rect_1 = Rectangle(10,20)
print(rect_1)
# Попробуем поменять
rect_1.width, rect_1.height = 5, 15
print(rect_1)
# Здесь все ок, все ожидаемо

# Теперь зададим параметры для квадрата
square_1 = Square(111)
rect_1.width, rect_1.height = square_1.width, square_1.height
print(rect_1)
print(square_1,f"\t#Ширина: {square_1.width}, Высота: {square_1.height}")
# Попроубем поменять какую - то одну из сторон, ожидаем, что изменится и высота, и ширина
square_1.height = 5
print(square_1, f"\t#Ширина: {square_1.width}, Высота: {square_1.height}")
# Теперь поменяем не высоту, а ширину
square_1.height = 13
print(square_1, f"\t#Ширина: {square_1.width}, Высота: {square_1.height}")
# Все выполняется правильно, при изменении какого из параметров (либо высота либо ширина), меняется другой (ширина или высота, соотвественно)



# Теперь попробуем написать класс из лекции, когда принцип нарушается, чтобы увидеть разницу наглядно

class BadSquare(Rectangle):

    def __init__(self, side, x=0, y=0):
        super().__init__(side, side, x, y)

# Сделаем всё тоже самое для квадрата , что написано выше , ожидаем, что какая - то из сторон квадрата будет различаться с другой
# (контрпример)
bad_square = BadSquare(111)
print(bad_square, f"\t#Ширина: {bad_square.width}, Высота: {bad_square.height}")
bad_square.height = 5
print(bad_square, f"\t#Ширина: {bad_square.width}, Высота: {bad_square.height}")
bad_square.height = 13
print(bad_square, f"\t#Ширина: {bad_square.width}, Высота: {bad_square.height}")
# Ну и тут видно, что всё плохо. Ширина меняется отдельно от высота, высота отдельно от ширины, так быть не должно.
