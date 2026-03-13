import tkinter as tk
from tkinter import messagebox, ttk

try:
    from PIL import Image, ImageGrab, ImageTk
except ImportError:
    Image = None
    ImageGrab = None
    ImageTk = None


def show_input_text(entry: tk.Entry, has_image: bool) -> None:
    text = entry.get()
    image_status = "あり" if has_image else "なし"
    messagebox.showinfo("入力内容", f"文字列: {text}\n画像: {image_status}")


def clear_thumbnail(image_label: tk.Label, close_button: tk.Button, state: dict) -> None:
    image_label.configure(image="", text="画像なし（Ctrl+Vで貼り付け）")
    image_label.image = None
    close_button.place_forget()
    state["has_image"] = False


def handle_paste_image(
    event: tk.Event,
    image_label: tk.Label,
    close_button: tk.Button,
    state: dict,
) -> str:
    if ImageGrab is None or ImageTk is None or Image is None:
        messagebox.showinfo("情報", "画像貼り付けには Pillow が必要です。")
        return "break"

    clipboard_data = ImageGrab.grabclipboard()
    if isinstance(clipboard_data, Image.Image):
        image = clipboard_data.copy()
        image.thumbnail((400, 240))
        tk_image = ImageTk.PhotoImage(image)

        image_label.configure(image=tk_image, text="")
        image_label.image = tk_image
        close_button.place(relx=1.0, rely=0.0, anchor="ne")
        state["has_image"] = True
        return "break"

    messagebox.showinfo("情報", "クリップボードに画像がありません。")
    return "break"


def main() -> None:
    root = tk.Tk()
    root.title("tkinter / ttk Button Sample 0004")

    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()

    window_width = screen_width // 2
    window_height = screen_height // 2

    pos_x = (screen_width - window_width) // 2
    pos_y = (screen_height - window_height) // 2

    root.geometry(f"{window_width}x{window_height}+{pos_x}+{pos_y}")

    frame = tk.Frame(root, padx=24, pady=24)
    frame.pack(expand=True)

    thumbnail_frame = tk.Frame(frame, relief="solid", bd=1)
    thumbnail_frame.pack(pady=(0, 12))

    image_label = tk.Label(
        thumbnail_frame,
        text="画像なし（Ctrl+Vで貼り付け）",
        width=40,
        height=10,
        anchor="center",
    )
    image_label.pack()

    state = {"has_image": False}

    close_button = tk.Button(
        thumbnail_frame,
        text="×",
        command=lambda: clear_thumbnail(image_label, close_button, state),
        padx=4,
        pady=0,
    )

    entry = tk.Entry(frame, width=40)
    entry.pack(pady=(0, 12))

    root.bind(
        "<Control-v>",
        lambda event: handle_paste_image(event, image_label, close_button, state),
    )
    root.bind(
        "<Control-V>",
        lambda event: handle_paste_image(event, image_label, close_button, state),
    )

    tk_button = tk.Button(
        frame,
        text="tkinter.Button",
        command=lambda: show_input_text(entry, state["has_image"]),
    )
    tk_button.pack(pady=(0, 12))

    ttk_button = ttk.Button(
        frame,
        text="ttk.Button",
        command=lambda: show_input_text(entry, state["has_image"]),
    )
    ttk_button.pack()

    root.mainloop()


if __name__ == "__main__":
    main()
