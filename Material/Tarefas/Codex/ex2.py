#Please, modify the code so that it returns a tuple containing all even values in i.
i=[1,2,3,4,5,6]

print((lambda i: tuple((-1 if j is None else j for j in i[1:4])))(i))