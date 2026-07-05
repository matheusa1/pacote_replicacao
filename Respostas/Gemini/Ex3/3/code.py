S=[1,2,3]
lst=[]
for f in S :
	for g in S:
		if f < g:
			lst.append((f,g))
print(lst)
