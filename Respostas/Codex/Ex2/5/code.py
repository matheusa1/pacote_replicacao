i = [1, 2, 3, 4, 5, 6]

print((lambda i: tuple(j for j in i if j % 2 == 0))(i))
