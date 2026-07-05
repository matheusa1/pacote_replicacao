ingredients = "salt pepper potato"
l = [list(x) for x in ingredients.split() if x.startswith("s")]
print(str(l))
