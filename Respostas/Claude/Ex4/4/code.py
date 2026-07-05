lst = []


class mod:
    name = "John"
    age = 36
    country = "Norway"
    _secret = "My secret password"


for n in dir(mod):
    if n[0] != "_":
        lst.append(n)
print(lst)
