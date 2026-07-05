ingredients = "solt pepper potato"
l = []

for x in ingredients.split():
    if x.startswith("s"):
        l.append(x)

print(str(l))
