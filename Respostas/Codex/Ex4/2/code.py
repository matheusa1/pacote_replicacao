lst = []


class mod:
    name = "John"
    age = 36
    country = "Norway"
    _secret = "My secret password"


lst = [value for key, value in mod.__dict__.items() if not key.startswith("_")]

print(lst)
