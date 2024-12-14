import numpy as np

class Quaternion:
    def __init__(self, w, x, y, z):
        self.q = np.array([w, x, y, z])

    def __add__(self, other):
        return Quaternion(*(self.q + other.q))

    def __sub__(self, other):
        return Quaternion(*(self.q - other.q))

    def __mul__(self, other):
        if isinstance(other, Quaternion):
            w1, x1, y1, z1 = self.q
            w2, x2, y2, z2 = other.q
            w = w1*w2 - x1*x2 - y1*y2 - z1*z2
            x = w1*x2 + x1*w2 + y1*z2 - z1*y2
            y = w1*y2 - x1*z2 + y1*w2 + z1*x2
            z = w1*z2 + x1*y2 - y1*x2 + z1*w2
            return Quaternion(w, x, y, z)
        else:
            return Quaternion(*(self.q * other))

    def __truediv__(self, other):
        if isinstance(other, Quaternion):
            conj = other.conjugate()
            norm_sq = other.norm() ** 2
            return self * conj * (1.0 / norm_sq)
        else:
            return Quaternion(*(self.q / other))

    def conjugate(self):
        w, x, y, z = self.q
        return Quaternion(w, -x, -y, -z)

    def norm(self):
        return np.linalg.norm(self.q)

    def inverse(self):
        conj = self.conjugate()
        norm_sq = self.norm() ** 2
        return Quaternion(*(conj.q / norm_sq))

    def angle(self):
        w = self.q[0]
        w = np.clip(w, -1.0, 1.0)
        return 2 * np.arccos(w)

    def notequal(self, other):
        return not np.array_equal(self.q, other.q)

    def sqrt(self):
        norm = self.norm()
        q = self.q / norm
        angle = np.arccos(np.clip(q[0], -1.0, 1.0))  # ограничение для косинуса (от -1 до 1)
        new_angle = angle / 2
        new_w = np.cos(new_angle)
        new_xyz = q[1:] * np.sin(new_angle) / np.sin(angle)
        return Quaternion(new_w, *new_xyz)

    def square(self):
        return self * self

    def rotate(self, vector):
        q_vector = Quaternion(0, *vector)
        rotated_vector = self * q_vector * self.conjugate()
        return rotated_vector.q[1:]

    def __repr__(self):
        return f"Quaternion({self.q[0]}, {self.q[1]}, {self.q[2]}, {self.q[3]})"


# Тестирование.
q1 = Quaternion(3, 3, 2, 8)
q2 = Quaternion(2, 8, 7, 4)
q3= Quaternion(0.7071, 0.7071, 0, 0)  # пример для поворота
vector = [1, 0, 0]
rotated_vector = q3.rotate(vector)

print("q1 + q2 =", q1 + q2)
print("q1 - q2 =", q1 - q2)
print("q1 * q2 =", q1 * q2)
print("q1 / q2 =", q1 / q2)
print("Сопряжение q1 =", q1.conjugate())
print("Норма q1 =", q1.norm())
print("Обратное значение =", q1.inverse())
print("Угол поворота q1 =", q1.angle())
print("Проверка на неравенство ", q1.notequal(q2))
print("Квадратный корень q1 =", q1.sqrt())
print("Квадрат q1 =", q1.square())
print("Перевернутый вектор =", rotated_vector)