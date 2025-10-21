import os

def module_setup() -> list:
    """
    Lists all module folders in the module directory
    Returns: indra_modules List of module folder names
    """

    # Clear existing list
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    modules_path = os.path.join(project_root, "modules")

    modulelist = []
    
    # Get all module names
    modulelist = os.listdir(modules_path)
    indra_modules = []

    for module in modulelist:
        # Add visible directories only
        if os.path.isdir(os.path.join(modules_path, module)) and not module.startswith('.'):
            indra_modules.append(module)
    return indra_modules
