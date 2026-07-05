# Please, modify the code so that only string values in the
# input list will be in the output list.

items=(2, 'pair',3,'odd')
l=[(x, x) for x in items]
print(l)