import os
import time
import tkinter as tk
from PIL import Image, ImageTk

class ImagePlayer(tk.Tk):
    def __init__(self, image_folder, frame_rate=2):
        super().__init__()
        self.image_folder = image_folder
        self.frame_rate = frame_rate
        self.images = []
        self.current_image_index = 0
        self.paused = True
        self.label = tk.Label(self)
        self.label.pack()

        self.load_images()
        self.check_new_images()
        self.play_images()

    def load_images(self):
        self.images = [
            os.path.join(self.image_folder, f)
            for f in sorted(os.listdir(self.image_folder))
            if f.endswith('.png')
        ]

    def check_new_images(self):
        if self.paused:
            self.load_images()
            if len(self.images) > self.current_image_index:
                self.paused = False

        self.after(1000, self.check_new_images)  # Check for new images every second

    def play_images(self):
        if not self.paused and self.current_image_index < len(self.images):
            img_path = self.images[self.current_image_index]
            img = Image.open(img_path)
            img = ImageTk.PhotoImage(img)
            self.label.config(image=img)
            self.label.image = img  # Keep a reference to avoid garbage collection
            self.current_image_index += 1
            self.after(int(1000 / self.frame_rate), self.play_images)
        elif self.current_image_index >= len(self.images):
            self.paused = True
