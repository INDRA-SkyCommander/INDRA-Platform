

def terminal_out(root, var, value):
    var.set(value)
    
    print(value)
    root.after(500, lambda: terminal_out(root, var, value))
    