#Please, modify the code so that it will return the length of x if it is a tuple or a list, otherwise return 1.
x=(1,2,3)

def function (x): 
	if isinstance(x, tuple):
		return sum(x) 
	else :
		return x

print(function(x))