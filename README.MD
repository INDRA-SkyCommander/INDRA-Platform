
<!-- Banner GIF -->
<img src="1,500 drones creating magic in the air - Imgur(1).gif" width=30% />


### Dependencies 
Run the following command from the same directory as "requirements.txt"
```bash
pip install -r requirements.txt
```

### Dev Notes

#### Package dependencies
At the end of your development session, before pushing your changes, run the following command to package up all of the dependencies and output them to "requirements.txt"
```bash
pip freeze > requirements.txt
```

#### GUI
* TKinter is being used to create the GUI, but TKinter looks very outdated. As a simple workaround for this, a theme is being used to easily update the look of the GUI. 
* This means your should use "ttk()" instead of "tk()" in most places.
* Example: 
```py
top_box = ttk.Frame(root, padding=(3, 3, 12, 12), style="box.TFrame")
```