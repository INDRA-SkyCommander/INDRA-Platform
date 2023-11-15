from os import listdir

modulelist = []
modulespath = "../modules"

modulelist = listdir(modulespath)

python_modules = []

def get_modules():
    for module in modulelist:
        
        if module.endswith(".py"):
            python_modules.append(module.removesuffix(".py"))
    return python_modules


