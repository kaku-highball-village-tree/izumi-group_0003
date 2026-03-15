import audioop
import ctypes
import io
import json
import os
import subprocess
import tempfile
import tkinter as tk
import wave
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

try:
    from vosk import KaldiRecognizer, Model
except ImportError:
    KaldiRecognizer = None
    Model = None


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




def create_audio_temp_file_path() -> str:
    temp_dir = tempfile.gettempdir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"voice_{timestamp}"
    first_path = os.path.join(temp_dir, f"{base_name}.wav")
    if not os.path.exists(first_path):
        return first_path

    index = 1
    while True:
        candidate = os.path.join(temp_dir, f"{base_name}_{index:04d}.wav")
        if not os.path.exists(candidate):
            return candidate
        index += 1


def _mci_send(command: str) -> int:
    return ctypes.windll.winmm.mciSendStringW(command, None, 0, None)


def _close_recorder_if_open(mic_state: dict) -> None:
    alias = mic_state.get("recording_alias", "recsound")
    _mci_send(f"close {alias}")


def get_vosk_model_path() -> str:
    # Pythonファイルの場所を基準に Vosk モデルのパスを解決する
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, "vosk-model-small-ja-0.22")


def transcribe_wav_with_vosk(wav_path: str) -> tuple[str | None, str | None]:
    # ライブラリ未導入時
    if Model is None or KaldiRecognizer is None:
        return None, "Vosk ライブラリが見つかりません。"

    # モデルフォルダ存在チェック
    model_path = get_vosk_model_path()
    if not os.path.isdir(model_path):
        return None, "Vosk モデルフォルダが見つかりません。"

    # 音声ファイル存在チェック
    if not os.path.exists(wav_path):
        return None, "wav ファイルが見つかりません。"

    # wav 読み込みとフォーマットチェック
    try:
        with wave.open(wav_path, "rb") as wav_file:
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            frame_rate = wav_file.getframerate()

            if channels < 1:
                return None, "wav のチャンネル数が不正です。"
            if sample_width not in (1, 2, 3, 4):
                return None, "対応外の wav 形式です。"

            model = Model(model_path)
            recognizer = KaldiRecognizer(model, frame_rate)
            recognizer.SetWords(True)

            texts: list[str] = []
            while True:
                chunk = wav_file.readframes(4000)
                if not chunk:
                    break

                # Vosk が扱いやすい 16bit PCM / モノラルへ変換する
                pcm_chunk = chunk
                if channels > 1:
                    pcm_chunk = audioop.tomono(pcm_chunk, sample_width, 0.5, 0.5)
                if sample_width == 1:
                    # 8bit PCM は符号なしのため、符号付きへ寄せてから 16bit 化
                    pcm_chunk = audioop.bias(pcm_chunk, 1, -128)
                    pcm_chunk = audioop.lin2lin(pcm_chunk, 1, 2)
                elif sample_width != 2:
                    pcm_chunk = audioop.lin2lin(pcm_chunk, sample_width, 2)

                if recognizer.AcceptWaveform(pcm_chunk):
                    result = json.loads(recognizer.Result())
                    text = result.get("text", "").strip()
                    if text:
                        texts.append(text)

            final_result = json.loads(recognizer.FinalResult())
            final_text = final_result.get("text", "").strip()
            if final_text:
                texts.append(final_text)
    except wave.Error:
        return None, "wav の読み込みに失敗しました。"
    except Exception:
        return None, "音声認識に失敗しました。"

    recognized_text = " ".join(texts).strip()
    if not recognized_text:
        return None, "音声を認識できませんでした。"

    return recognized_text, None


def on_mic_button_click(mic_button: tk.Button, mic_state: dict, temp_files: set[str]) -> None:
    if os.name != "nt":
        messagebox.showinfo("録音", "録音機能は Windows のみ対応です。")
        return

    alias = mic_state["recording_alias"]

    if not mic_state["is_recording"]:
        _close_recorder_if_open(mic_state)
        open_result = _mci_send(f"open new type waveaudio alias {alias}")
        if open_result != 0:
            messagebox.showinfo("録音", "録音デバイスを開始できませんでした。")
            return

        record_result = _mci_send(f"record {alias}")
        if record_result != 0:
            _close_recorder_if_open(mic_state)
            messagebox.showinfo("録音", "録音を開始できませんでした。")
            return

        mic_state["is_recording"] = True
        mic_button.configure(text="●録音中", fg="red")
        return

    audio_path = create_audio_temp_file_path()
    stop_result = _mci_send(f"stop {alias}")
    save_result = _mci_send(f'save {alias} "{audio_path}"')
    _close_recorder_if_open(mic_state)

    if stop_result != 0 or save_result != 0:
        messagebox.showinfo("録音", "録音ファイルの保存に失敗しました。")
        mic_state["is_recording"] = False
        mic_button.configure(text="🎤", fg="black")
        return

    temp_files.add(audio_path)
    mic_state["last_audio_path"] = audio_path
    mic_state["is_recording"] = False

    # 録音停止後に Vosk で文字起こし（第5段階: print + MessageBox まで）
    mic_button.configure(text="変換中...", fg="black")
    recognized_text, error_message = transcribe_wav_with_vosk(audio_path)
    mic_button.configure(text="🎤", fg="black")

    if error_message is not None:
        messagebox.showinfo("音声認識", error_message)
        return

    print(recognized_text)
    messagebox.showinfo("音声認識結果", recognized_text)


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


def cleanup_temp_files(root: tk.Tk, temp_files: set[str], mic_state: dict) -> None:
    if os.name == "nt" and mic_state.get("is_recording"):
        _close_recorder_if_open(mic_state)

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

    root.title("tkinter / ttk Button Sample 0012")

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

    mic_state = {"is_recording": False, "recording_alias": "recsound", "last_audio_path": None}

    mic_button = tk.Button(
        entry_row,
        text="🎤",
        command=lambda: on_mic_button_click(mic_button, mic_state, temp_files),
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

    root.protocol("WM_DELETE_WINDOW", lambda: cleanup_temp_files(root, temp_files, mic_state))

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
