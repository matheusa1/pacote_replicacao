x = (1, 2, 3)


def function(x):
    if isinstance(x, (tuple, list)):
        return len(x)
    return 1


print(function(x))
