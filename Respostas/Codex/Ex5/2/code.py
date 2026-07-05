import numpy as np

output = np.array([[2, 3], [4, 5]])
lst = []

for x in output:
    if len(x) == 2:
        lst.append(x.tolist())

print(lst)
