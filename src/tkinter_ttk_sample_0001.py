import tkinter as tk
from tkinter import ttk


def do_nothing() -> None:
    pass


def main() -> None:
    root = tk.Tk()
    root.title("tkinter / ttk Button Sample")

    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()

    window_width = screen_width // 2
    window_height = screen_height // 2

    pos_x = (screen_width - window_width) // 2
    pos_y = (screen_height - window_height) // 2

    root.geometry(f"{window_width}x{window_height}+{pos_x}+{pos_y}")

    frame = tk.Frame(root, padx=24, pady=24)
    frame.pack(expand=True)

    tk_button = tk.Button(frame, text="tkinter.Button", command=do_nothing)
    tk_button.pack(pady=(0, 12))

    ttk_button = ttk.Button(frame, text="ttk.Button", command=do_nothing)
    ttk_button.pack()

    root.mainloop()


if __name__ == "__main__":
    main()
