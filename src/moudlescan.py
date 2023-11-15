from os import listdir

modulelist = []
modulespath = "../modules"

modulelist = listdir(modulespath)

for module in modulelist:
    module.strip()
    print(module)
    modulelist.remove(module)
    if ".py" in module:
        module = module.removesuffix(".py")
        modulelist.append(module)

        

           



#print(modulelist)


