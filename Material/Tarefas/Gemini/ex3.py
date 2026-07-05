# Please, modify the code so that the list generated in output will 
# contain all the combinations of the elements in S.

S=[1,2,3]
lst=[]
for f in S :
	for g in S:
		if f != g:
			lst.append((f,g))
print(lst)