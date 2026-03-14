import tkinter as tk
from tkinter import messagebox, ttk

try:
    from PIL import Image, ImageGrab, ImageTk
except ImportError:  # Pillow がない環境でも起動だけは可能にする
    Image = None
    ImageGrab = None
    ImageTk = None


def show_input_text(entry: tk.Entry, has_image: bool) -> None:
    text = entry.get()
    image_status = "あり" if has_image else "なし"
    messagebox.showinfo("入力内容", f"文字列: {text}\n画像: {image_status}")


def handle_paste_image(
    event: tk.Event,
    preview_label: tk.Label,
    state: dict,
) -> str | None:
    if ImageGrab is None or ImageTk is None or Image is None:
        messagebox.showinfo("情報", "画像貼り付けには Pillow が必要です。")
        return "break"

    clipboard_data = ImageGrab.grabclipboard()

    if isinstance(clipboard_data, Image.Image):
        image = clipboard_data.copy()
        image.thumbnail((320, 180))
        tk_image = ImageTk.PhotoImage(image)

        preview_label.configure(image=tk_image, text="")
        preview_label.image = tk_image
        state["has_image"] = True
        return "break"

    messagebox.showinfo("情報", "クリップボードに画像がありません。")
    return "break"


def main() -> None:
    root = tk.Tk()
    root.title("tkinter / ttk Button Sample 0003")

    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()

    window_width = screen_width // 2
    window_height = screen_height // 2

    pos_x = (screen_width - window_width) // 2
    pos_y = (screen_height - window_height) // 2

    root.geometry(f"{window_width}x{window_height}+{pos_x}+{pos_y}")

    frame = tk.Frame(root, padx=24, pady=24)
    frame.pack(expand=True)

    preview_label = tk.Label(
        frame,
        text="画像なし（Ctrl+Vで貼り付け）",
        width=40,
        height=10,
        relief="solid",
        anchor="center",
    )
    preview_label.pack(pady=(0, 12))

    entry = tk.Entry(frame, width=40)
    entry.pack(pady=(0, 12))

    state = {"has_image": False}

    root.bind(
        "<Control-v>",
        lambda event: handle_paste_image(event, preview_label, state),
    )
    root.bind(
        "<Control-V>",
        lambda event: handle_paste_image(event, preview_label, state),
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
