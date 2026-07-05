#Please, modify the code so that it will output a list only composed of the values of all non private class attributes.
lst=[]
class mod:
  name = "John"
  age = 36
  country = "Norway"
  _secret= "My secret password"
  
lst=[n for n in dir(mod) if n[0] != '_']

print(lst)