# Please, modify the function so that it will return a tuple containing all evens values in i

i = [1, 2, 3, 4, 5, 6]


def function(i):
    return tuple((-1 if j is None else j for j in i[1:4]))


print(function(i))
