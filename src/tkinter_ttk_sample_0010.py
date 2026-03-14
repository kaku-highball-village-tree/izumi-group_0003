import io
import os
import subprocess
import tempfile
import tkinter as tk
from datetime import datetime
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


MAX_API_FILE_SIZE = 10 * 1024 * 1024
THUMBNAIL_SIZE = (400, 240)


def open_original_temp_with_paint(current_image: dict) -> None:
    original_temp_path = current_image["original_temp_path"]
    if original_temp_path is None:
        messagebox.showinfo("Paint起動", "原寸tempファイルはありません。")
        return

    try:
        subprocess.Popen(["mspaint", original_temp_path])
    except OSError:
        messagebox.showinfo("Paint起動", "Paint を起動できませんでした。")




def on_mic_button_click(mic_button: tk.Button, mic_state: dict) -> None:
    mic_state["is_recording"] = not mic_state["is_recording"]
    if mic_state["is_recording"]:
        mic_button.configure(text="🔴録音中")
    else:
        mic_button.configure(text="🎤")

def create_temp_file_path(extension: str) -> str:
    temp_dir = tempfile.gettempdir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"img_{timestamp}"
    first_path = os.path.join(temp_dir, f"{base_name}.{extension}")
    if not os.path.exists(first_path):
        return first_path

    index = 1
    while True:
        candidate = os.path.join(temp_dir, f"{base_name}_{index:02d}.{extension}")
        if not os.path.exists(candidate):
            return candidate
        index += 1


def save_original_temp_image(image: Image.Image, temp_files: set[str]) -> str:
    temp_path = create_temp_file_path("png")
    image.save(temp_path, format="PNG")
    temp_files.add(temp_path)
    return temp_path


def save_api_send_image(original_temp_path: str, temp_files: set[str]) -> str:
    if os.path.getsize(original_temp_path) <= MAX_API_FILE_SIZE:
        return original_temp_path

    if Image is None:
        return original_temp_path

    with Image.open(original_temp_path) as original:
        work = original.convert("RGB")

    quality = 95
    while True:
        buffer = io.BytesIO()
        work.save(buffer, format="JPEG", quality=quality, optimize=True)
        data = buffer.getvalue()

        if len(data) <= MAX_API_FILE_SIZE:
            temp_path = create_temp_file_path("jpg")
            with open(temp_path, "wb") as temp_file:
                temp_file.write(data)
            temp_files.add(temp_path)
            return temp_path

        if quality > 35:
            quality -= 10
            continue

        width, height = work.size
        if max(width, height) <= 640:
            temp_path = create_temp_file_path("jpg")
            with open(temp_path, "wb") as temp_file:
                temp_file.write(data)
            temp_files.add(temp_path)
            return temp_path

        scale = 0.8
        resized = (max(1, int(width * scale)), max(1, int(height * scale)))
        work = work.resize(resized, Image.LANCZOS)
        quality = 90


def make_snapshot(current_image: dict) -> dict:
    image = current_image["pil"]
    if image is None:
        return {"image": None, "original_temp_path": None, "api_send_path": None}

    return {
        "image": image.copy(),
        "original_temp_path": current_image["original_temp_path"],
        "api_send_path": current_image["api_send_path"],
    }


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
        current_image["original_temp_path"] = None
        current_image["api_send_path"] = None
        return

    tk_image = ImageTk.PhotoImage(image)
    image_label.configure(image=tk_image, text="")
    image_label.image = tk_image
    close_button.place(relx=1.0, rely=0.0, anchor="ne")
    state["has_image"] = True
    current_image["pil"] = image.copy()
    current_image["original_temp_path"] = snapshot["original_temp_path"]
    current_image["api_send_path"] = snapshot["api_send_path"]


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
        {"image": None, "original_temp_path": None, "api_send_path": None},
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
    temp_files: set[str],
) -> str:
    if ImageGrab is None or ImageTk is None or Image is None:
        messagebox.showinfo("情報", "Pillow が必要です（Pillowあり: サムネイル化される）。")
        return "break"

    clipboard_data = ImageGrab.grabclipboard()
    if isinstance(clipboard_data, Image.Image):
        history["undo"].append(make_snapshot(current_image))
        history["redo"].clear()

        original = clipboard_data.copy()
        original_temp_path = save_original_temp_image(original, temp_files)
        api_send_path = save_api_send_image(original_temp_path, temp_files)

        preview = original.copy()
        preview.thumbnail(THUMBNAIL_SIZE)
        apply_snapshot(
            {
                "image": preview,
                "original_temp_path": original_temp_path,
                "api_send_path": api_send_path,
            },
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
    temp_files: set[str],
) -> str:
    if Image is None or ImageTk is None:
        messagebox.showinfo("情報", "画像のドラッグ＆ドロップには Pillow が必要です。")
        return "break"

    drop_files = root.tk.splitlist(event.data)
    if not drop_files:
        return "break"

    image_path = drop_files[0]
    try:
        with Image.open(image_path) as loaded:
            original = loaded.copy()
    except Exception:
        messagebox.showinfo("情報", "画像ファイルを読み込めませんでした。")
        return "break"

    history["undo"].append(make_snapshot(current_image))
    history["redo"].clear()

    original_temp_path = save_original_temp_image(original, temp_files)
    api_send_path = save_api_send_image(original_temp_path, temp_files)

    preview = original.copy()
    preview.thumbnail(THUMBNAIL_SIZE)
    apply_snapshot(
        {
            "image": preview,
            "original_temp_path": original_temp_path,
            "api_send_path": api_send_path,
        },
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


def cleanup_temp_files(root: tk.Tk, temp_files: set[str]) -> None:
    for file_path in list(temp_files):
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except OSError:
            pass
    root.destroy()


def main() -> None:
    if TkinterDnD is not None:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()

    root.title("tkinter / ttk Button Sample 0010")

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
    current_image = {
        "pil": None,
        "original_temp_path": None,
        "api_send_path": None,
    }
    history = {"undo": [], "redo": []}
    temp_files: set[str] = set()

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

    entry_row = tk.Frame(frame)
    entry_row.pack(pady=(0, 12))

    entry = tk.Entry(entry_row, width=40)
    entry.pack(side="left")

    mic_state = {"is_recording": False}

    mic_button = tk.Button(
        entry_row,
        text="🎤",
        command=lambda: on_mic_button_click(mic_button, mic_state),
    )
    mic_button.pack(side="left", padx=(8, 0))

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
                temp_files,
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
            temp_files,
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
            temp_files,
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

    root.protocol("WM_DELETE_WINDOW", lambda: cleanup_temp_files(root, temp_files))

    tk_button = tk.Button(
        frame,
        text="tkinter.Button",
        command=lambda: open_original_temp_with_paint(current_image),
    )
    tk_button.pack(pady=(0, 12))

    ttk_button = ttk.Button(
        frame,
        text="ttk.Button",
        command=lambda: open_original_temp_with_paint(current_image),
    )
    ttk_button.pack()

    root.mainloop()


if __name__ == "__main__":
    main()
