import ctypes
import io
import os
import shutil
import subprocess
import tempfile
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk

from cryptography.fernet import Fernet
from openai import OpenAI

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




def create_audio_temp_file_path() -> str:
    """録音用の一時 WAV ファイルパスを生成する。"""
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


def create_mp3_temp_file_path_from_wav(wav_path: str) -> str:
    """WAV と同じタイムスタンプを使った MP3 一時ファイルパスを返す。"""
    wav_obj = Path(wav_path)
    return str(wav_obj.with_suffix('.mp3'))


def find_ffmpeg_executable_path() -> str | None:
    """同じフォルダー、次に PATH 上から ffmpeg 実行ファイルを探す。"""
    script_dir = Path(__file__).resolve().parent
    local_ffmpeg_path = script_dir / "ffmpeg.exe"
    if local_ffmpeg_path.exists():
        return str(local_ffmpeg_path)

    return shutil.which("ffmpeg")


def load_api_key_from_encrypted_files() -> str:
    """secret_key.bin と encrypted_key.bin から OpenAI API キーを復号する。"""
    script_dir = Path(__file__).resolve().parent
    candidate_directories = [
        script_dir,
        script_dir.parent,
    ]
    secret_key_path = None
    encrypted_key_path = None

    for base_dir in candidate_directories:
        candidate_secret_key_path = base_dir / "key" / "secret_key.bin"
        candidate_encrypted_key_path = base_dir / "ciphertext" / "encrypted_key.bin"
        if candidate_secret_key_path.exists() and candidate_encrypted_key_path.exists():
            secret_key_path = candidate_secret_key_path
            encrypted_key_path = candidate_encrypted_key_path
            break

    if secret_key_path is None or encrypted_key_path is None:
        raise FileNotFoundError("secret_key.bin または encrypted_key.bin が見つかりません。")

    with open(secret_key_path, 'rb') as secret_key_file:
        secret_key = secret_key_file.read()

    cipher = Fernet(secret_key)

    with open(encrypted_key_path, 'rb') as encrypted_key_file:
        encrypted_token = encrypted_key_file.read()

    return cipher.decrypt(encrypted_token).decode('utf-8')


def convert_wav_to_mp3(wav_path: str, mp3_path: str, ffmpeg_path: str) -> None:
    """ffmpeg を使って WAV を MP3 に変換する。"""
    subprocess.run(
        [
            ffmpeg_path,
            '-y',
            '-i',
            wav_path,
            mp3_path,
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def transcribe_audio_file(audio_file_path: str, api_key: str) -> str:
    """音声ファイルを OpenAI API に送信して文字起こし結果を返す。"""
    client = OpenAI(api_key=api_key)

    with open(audio_file_path, 'rb') as audio_file:
        response = client.audio.transcriptions.create(
            model='gpt-4o-mini-transcribe',
            file=audio_file,
        )

    return response.text


def save_transcription_to_file(target_directory_path: str, transcribed_text: str) -> str:
    """文字起こし結果を日時付きテキストファイルとして保存する。"""
    timestamp = datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
    output_file_name = f'output_voice_string_{timestamp}.txt'
    output_file_path = os.path.join(target_directory_path, output_file_name)

    with open(output_file_path, 'w', encoding='utf-8') as text_file:
        text_file.write(transcribed_text)
        text_file.write('\n')

    return output_file_path


def open_text_file_with_default_editor(file_path: str) -> None:
    """保存したテキストファイルを標準エディターで開く。"""
    os.startfile(file_path)


def _mci_send(command: str) -> int:
    return ctypes.windll.winmm.mciSendStringW(command, None, 0, None)


def _close_recorder_if_open(mic_state: dict) -> None:
    alias = mic_state.get("recording_alias", "recsound")
    _mci_send(f"close {alias}")




def on_mic_button_click(mic_button: tk.Button, mic_state: dict, temp_files: set[str]) -> None:
    """録音ボタンの押下で録音開始 / 停止と文字起こし処理を行う。"""
    if os.name != 'nt':
        messagebox.showinfo('録音', '録音機能は Windows のみ対応です。')
        return

    alias = mic_state['recording_alias']

    if not mic_state['is_recording']:
        _close_recorder_if_open(mic_state)
        open_result = _mci_send(f'open new type waveaudio alias {alias}')
        if open_result != 0:
            messagebox.showinfo('録音失敗', '録音デバイスを開始できませんでした。')
            return

        record_result = _mci_send(f'record {alias}')
        if record_result != 0:
            _close_recorder_if_open(mic_state)
            messagebox.showinfo('録音失敗', '録音を開始できませんでした。')
            return

        mic_state['is_recording'] = True
        mic_button.configure(text='●録音中', fg='red')
        return

    wav_path = create_audio_temp_file_path()
    mp3_path = create_mp3_temp_file_path_from_wav(wav_path)

    stop_result = _mci_send(f'stop {alias}')
    save_result = _mci_send(f'save {alias} "{wav_path}"')
    _close_recorder_if_open(mic_state)

    mic_state['is_recording'] = False
    mic_button.configure(text='変換中...', fg='black')

    if stop_result != 0:
        mic_button.configure(text='🎤', fg='black')
        messagebox.showinfo('録音失敗', '録音の停止に失敗しました。')
        return

    if save_result != 0:
        mic_button.configure(text='🎤', fg='black')
        messagebox.showinfo('WAV保存失敗', '録音ファイルの保存に失敗しました。')
        return

    temp_files.add(wav_path)
    mic_state['last_audio_path'] = wav_path
    ffmpeg_path = find_ffmpeg_executable_path()
    transcription_source_path = wav_path
    mp3_conversion_message = None

    if ffmpeg_path is not None:
        try:
            convert_wav_to_mp3(wav_path, mp3_path, ffmpeg_path)
            temp_files.add(mp3_path)
            transcription_source_path = mp3_path
        except Exception as exc:
            mp3_conversion_message = f'MP3変換失敗のため WAV を送信します。\n{exc}'
    else:
        mp3_conversion_message = 'ffmpeg が見つからないため WAV を送信します。'

    try:
        api_key = load_api_key_from_encrypted_files()
    except Exception as exc:
        mic_button.configure(text='🎤', fg='black')
        messagebox.showinfo('APIキー復号失敗', f'OpenAI API キーの復号に失敗しました。\n{exc}')
        return

    try:
        recognized_text = transcribe_audio_file(transcription_source_path, api_key)
    except Exception as exc:
        mic_button.configure(text='🎤', fg='black')
        messagebox.showinfo('API送信失敗', f'音声の送信または文字起こしに失敗しました。\n{exc}')
        return

    try:
        output_directory = os.path.dirname(wav_path)
        saved_text_path = save_transcription_to_file(output_directory, recognized_text)
    except Exception as exc:
        mic_button.configure(text='🎤', fg='black')
        messagebox.showinfo('保存失敗', f'文字起こし結果の保存に失敗しました。\n{exc}')
        return

    mic_button.configure(text='🎤', fg='black')
    if mp3_conversion_message is not None:
        messagebox.showinfo('MP3変換', mp3_conversion_message)
    messagebox.showinfo(
        '音声認識結果',
        f'{recognized_text}\n\n保存先: {saved_text_path}',
    )

    try:
        open_text_file_with_default_editor(saved_text_path)
    except Exception as exc:
        messagebox.showinfo('エディター起動失敗', f'保存したテキストファイルを開けませんでした。\n{exc}')


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
