import os


modulelist = []
modulespath = os.path.dirname(__file__) + "/../modules/"

print(modulespath)

modulelist = os.listdir(modulespath)

python_modules = []

def get_modules():
    for module in modulelist:
        
        if module.endswith(".py"):
            python_modules.append(module.removesuffix(".py"))
    return python_modules


