from os import listdir

modulelist = []
modulespath = "../modules"

modulelist = listdir(modulespath)

python_modules = []

print(modulelist)

for module in modulelist:
    
    if module.endswith(".py"):
        python_modules.append(module.removesuffix(".py"))
    
print(python_modules)



