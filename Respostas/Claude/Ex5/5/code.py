import numpy as np

output = np.array([[2, 3], [4, 5]])
print(list(filter(lambda x: len(x) == 2, output)))
