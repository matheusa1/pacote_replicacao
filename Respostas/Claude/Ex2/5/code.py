i = [1, 2, 3, 4, 5, 6]


def function(i):
    return tuple(j for j in i if j is not None and j % 2 == 0)


print(function(i))
