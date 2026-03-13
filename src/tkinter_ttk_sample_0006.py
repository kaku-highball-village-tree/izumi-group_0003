import tkinter as tk
from tkinter import messagebox, ttk

try:
    from PIL import Image, ImageGrab, ImageTk
except ImportError:
    Image = None
    ImageGrab = None
    ImageTk = None

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    DND_FILES = None
    TkinterDnD = None


def show_input_text(entry: tk.Entry, has_image: bool) -> None:
    text = entry.get()
    image_status = "あり" if has_image else "なし"
    messagebox.showinfo("入力内容", f"文字列: {text}\n画像: {image_status}")


def make_snapshot(current_image: dict) -> dict:
    image = current_image["pil"]
    if image is None:
        return {"image": None}
    return {"image": image.copy()}


def apply_snapshot(
    snapshot: dict,
    image_label: tk.Label,
    close_button: tk.Button,
    state: dict,
    current_image: dict,
) -> None:
    image = snapshot["image"]
    if image is None or ImageTk is None:
        image_label.configure(image="", text="画像なし（Ctrl+V / D&D で貼り付け）")
        image_label.image = None
        close_button.place_forget()
        state["has_image"] = False
        current_image["pil"] = None
        return

    tk_image = ImageTk.PhotoImage(image)
    image_label.configure(image=tk_image, text="")
    image_label.image = tk_image
    close_button.place(relx=1.0, rely=0.0, anchor="ne")
    state["has_image"] = True
    current_image["pil"] = image.copy()


def clear_thumbnail(
    image_label: tk.Label,
    close_button: tk.Button,
    state: dict,
    current_image: dict,
    history: dict,
) -> None:
    history["undo"].append(make_snapshot(current_image))
    history["redo"].clear()
    apply_snapshot(
        {"image": None},
        image_label,
        close_button,
        state,
        current_image,
    )


def handle_paste_image(
    event: tk.Event,
    image_label: tk.Label,
    close_button: tk.Button,
    state: dict,
    current_image: dict,
    history: dict,
) -> str:
    if ImageGrab is None or ImageTk is None or Image is None:
        messagebox.showinfo("情報", "Pillow が必要です（Pillowあり: サムネイル化される）。")
        return "break"

    clipboard_data = ImageGrab.grabclipboard()
    if isinstance(clipboard_data, Image.Image):
        history["undo"].append(make_snapshot(current_image))
        history["redo"].clear()

        image = clipboard_data.copy()
        image.thumbnail((800, 480))
        apply_snapshot(
            {"image": image},
            image_label,
            close_button,
            state,
            current_image,
        )
        return "break"

    messagebox.showinfo("情報", "クリップボードに画像がありません。")
    return "break"


def handle_drop_image_file(
    event: tk.Event,
    root: tk.Tk,
    image_label: tk.Label,
    close_button: tk.Button,
    state: dict,
    current_image: dict,
    history: dict,
) -> str:
    if Image is None or ImageTk is None:
        messagebox.showinfo("情報", "画像のドラッグ＆ドロップには Pillow が必要です。")
        return "break"

    drop_files = root.tk.splitlist(event.data)
    if not drop_files:
        return "break"

    image_path = drop_files[0]
    try:
        image = Image.open(image_path)
        image.thumbnail((800, 480))
    except Exception:
        messagebox.showinfo("情報", "画像ファイルを読み込めませんでした。")
        return "break"

    history["undo"].append(make_snapshot(current_image))
    history["redo"].clear()
    apply_snapshot(
        {"image": image.copy()},
        image_label,
        close_button,
        state,
        current_image,
    )
    return "break"


def undo_thumbnail(
    event: tk.Event,
    image_label: tk.Label,
    close_button: tk.Button,
    state: dict,
    current_image: dict,
    history: dict,
) -> str:
    if not history["undo"]:
        return "break"

    history["redo"].append(make_snapshot(current_image))
    snapshot = history["undo"].pop()
    apply_snapshot(snapshot, image_label, close_button, state, current_image)
    return "break"


def redo_thumbnail(
    event: tk.Event,
    image_label: tk.Label,
    close_button: tk.Button,
    state: dict,
    current_image: dict,
    history: dict,
) -> str:
    if not history["redo"]:
        return "break"

    history["undo"].append(make_snapshot(current_image))
    snapshot = history["redo"].pop()
    apply_snapshot(snapshot, image_label, close_button, state, current_image)
    return "break"


def main() -> None:
    if TkinterDnD is not None:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()

    root.title("tkinter / ttk Button Sample 0006")

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
        text="画像なし（Ctrl+V / D&D で貼り付け）",
        anchor="nw",
    )
    image_label.pack()

    state = {"has_image": False}
    current_image = {"pil": None}
    history = {"undo": [], "redo": []}

    close_button = tk.Button(
        thumbnail_frame,
        text="×",
        command=lambda: clear_thumbnail(
            image_label,
            close_button,
            state,
            current_image,
            history,
        ),
        padx=4,
        pady=0,
    )

    entry = tk.Entry(frame, width=40)
    entry.pack(pady=(0, 12))

    if DND_FILES is not None:
        thumbnail_frame.drop_target_register(DND_FILES)
        thumbnail_frame.dnd_bind(
            "<<Drop>>",
            lambda event: handle_drop_image_file(
                event,
                root,
                image_label,
                close_button,
                state,
                current_image,
                history,
            ),
        )

    root.bind(
        "<Control-v>",
        lambda event: handle_paste_image(
            event,
            image_label,
            close_button,
            state,
            current_image,
            history,
        ),
    )
    root.bind(
        "<Control-V>",
        lambda event: handle_paste_image(
            event,
            image_label,
            close_button,
            state,
            current_image,
            history,
        ),
    )
    root.bind(
        "<Control-z>",
        lambda event: undo_thumbnail(
            event,
            image_label,
            close_button,
            state,
            current_image,
            history,
        ),
    )
    root.bind(
        "<Control-Z>",
        lambda event: undo_thumbnail(
            event,
            image_label,
            close_button,
            state,
            current_image,
            history,
        ),
    )
    root.bind(
        "<Control-y>",
        lambda event: redo_thumbnail(
            event,
            image_label,
            close_button,
            state,
            current_image,
            history,
        ),
    )
    root.bind(
        "<Control-Y>",
        lambda event: redo_thumbnail(
            event,
            image_label,
            close_button,
            state,
            current_image,
            history,
        ),
    )
    root.bind(
        "<Control-Shift-Z>",
        lambda event: redo_thumbnail(
            event,
            image_label,
            close_button,
            state,
            current_image,
            history,
        ),
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
