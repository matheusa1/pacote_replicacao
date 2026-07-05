# Please, modify the code so that it will return only the sub-lists having a size equal to 2.

import numpy as np

output = (np.array([[2, 3], [4, 5]])).flatten()
print(list(filter(lambda x: x, output)))
