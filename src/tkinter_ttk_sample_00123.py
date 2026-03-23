import base64
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
IMAGE_OCR_CONFIRM_TIMEOUT_MS = 10000
IMAGE_OCR_MODEL = "gpt-4.1-mini"


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


def create_bom_temp_file_from_text_file(source_file_path: str, temp_files: set[str]) -> str:
    """表示専用の BOM 付き temp ファイルを作成する。"""
    source_path = Path(source_file_path)
    bom_file_name = f"bom_temp_{source_path.name}"
    bom_file_path = source_path.with_name(bom_file_name)

    with open(source_file_path, "r", encoding="utf-8") as source_file:
        content = source_file.read()

    with open(bom_file_path, "w", encoding="utf-8-sig") as bom_file:
        bom_file.write(content)

    temp_files.add(str(bom_file_path))
    return str(bom_file_path)


def open_text_file_with_notepad_and_delete_after_close(file_path: str, temp_files: set[str]) -> None:
    """メモ帳で開き、閉じられたら BOM 付き temp ファイルを削除する。"""
    process = subprocess.Popen(["notepad.exe", file_path])
    process.wait()

    if file_path in temp_files:
        temp_files.discard(file_path)

    if os.path.exists(file_path):
        os.remove(file_path)


def save_image_ocr_to_file(target_directory_path: str, recognized_text: str) -> str:
    """画像OCR結果を日時付きテキストファイルとして保存する。"""
    timestamp = datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
    output_file_name = f'output_image_string_{timestamp}.txt'
    output_file_path = os.path.join(target_directory_path, output_file_name)

    with open(output_file_path, 'w', encoding='utf-8') as text_file:
        text_file.write(recognized_text)
        text_file.write('\n')

    return output_file_path


def _encode_image_file_as_data_url(image_file_path: str) -> str:
    image_path = Path(image_file_path)
    suffix = image_path.suffix.lower()
    mime_type_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    mime_type = mime_type_map.get(suffix, "application/octet-stream")

    with open(image_file_path, "rb") as image_file:
        encoded = base64.b64encode(image_file.read()).decode("ascii")

    return f"data:{mime_type};base64,{encoded}"


def extract_text_from_image_file(image_file_path: str, api_key: str) -> str:
    """画像ファイルを OpenAI API に送信して OCR 結果文字列を返す。"""
    client = OpenAI(api_key=api_key)
    data_url = _encode_image_file_as_data_url(image_file_path)

    response = client.responses.create(
        model=IMAGE_OCR_MODEL,
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": "画像内の文字をOCRしてください。読めた文字だけを自然な改行で返してください。",
                    },
                    {
                        "type": "input_image",
                        "image_url": data_url,
                    },
                ],
            }
        ],
    )

    return response.output_text.strip()


def ask_image_ocr_confirmation(root: tk.Tk) -> str:
    """画像OCRを実行するか確認し、yes/no/timeout を返す。"""
    dialog = tk.Toplevel(root)
    dialog.title("画像OCR確認")
    dialog.transient(root)
    dialog.grab_set()
    dialog.resizable(False, False)

    result = {"value": "timeout"}

    frame = tk.Frame(dialog, padx=16, pady=16)
    frame.pack()

    tk.Label(
        frame,
        text="画像を ChatGPT に送って OCR を実行しますか？\nYes: 実行 / No: やり直し / 10秒放置: やり直し",
        justify="left",
    ).pack(pady=(0, 12))

    button_row = tk.Frame(frame)
    button_row.pack()

    def close_dialog(value: str) -> None:
        if dialog.winfo_exists():
            result["value"] = value
            dialog.destroy()

    tk.Button(button_row, text="Yes", width=10, command=lambda: close_dialog("yes")).pack(side="left", padx=4)
    tk.Button(button_row, text="No", width=10, command=lambda: close_dialog("no")).pack(side="left", padx=4)

    dialog.protocol("WM_DELETE_WINDOW", lambda: close_dialog("no"))
    dialog.after(IMAGE_OCR_CONFIRM_TIMEOUT_MS, lambda: close_dialog("timeout"))

    dialog.update_idletasks()
    pos_x = root.winfo_rootx() + max(0, (root.winfo_width() - dialog.winfo_width()) // 2)
    pos_y = root.winfo_rooty() + max(0, (root.winfo_height() - dialog.winfo_height()) // 2)
    dialog.geometry(f"+{pos_x}+{pos_y}")

    root.wait_window(dialog)
    return result["value"]


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
        bom_temp_file_path = create_bom_temp_file_from_text_file(saved_text_path, temp_files)
        open_text_file_with_notepad_and_delete_after_close(bom_temp_file_path, temp_files)
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


def run_image_ocr_flow(
    root: tk.Tk,
    image_label: tk.Label,
    close_button: tk.Button,
    state: dict,
    current_image: dict,
    history: dict,
    temp_files: set[str],
) -> None:
    """現在の画像に対する OCR 実行可否を確認し、必要なら OCR を実行する。"""
    confirm_result = ask_image_ocr_confirmation(root)
    if confirm_result != "yes":
        clear_thumbnail(image_label, close_button, state, current_image, history)
        if confirm_result == "timeout":
            messagebox.showinfo("画像OCR", "一定時間応答がなかったため、画像をクリアしました。")
        return

    api_send_path = current_image.get("api_send_path")
    if not api_send_path:
        messagebox.showinfo("画像OCR", "OCR に使用できる画像がありません。")
        return

    try:
        api_key = load_api_key_from_encrypted_files()
    except Exception as exc:
        messagebox.showinfo("APIキー復号失敗", f"OpenAI API キーの復号に失敗しました。\n{exc}")
        return

    try:
        recognized_text = extract_text_from_image_file(api_send_path, api_key)
    except Exception as exc:
        messagebox.showinfo("画像OCR失敗", f"画像の OCR に失敗しました。\n{exc}")
        return

    try:
        saved_text_path = save_image_ocr_to_file(os.path.dirname(api_send_path), recognized_text)
    except Exception as exc:
        messagebox.showinfo("保存失敗", f"画像OCR結果の保存に失敗しました。\n{exc}")
        return

    messagebox.showinfo(
        "画像OCR結果",
        f"{recognized_text}\n\n保存先: {saved_text_path}",
    )

    try:
        bom_temp_file_path = create_bom_temp_file_from_text_file(saved_text_path, temp_files)
        open_text_file_with_notepad_and_delete_after_close(bom_temp_file_path, temp_files)
    except Exception as exc:
        messagebox.showinfo("エディター起動失敗", f"保存したテキストファイルを開けませんでした。\n{exc}")


def handle_paste_image(
    event: tk.Event,
    root: tk.Tk,
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
        run_image_ocr_flow(
            root,
            image_label,
            close_button,
            state,
            current_image,
            history,
            temp_files,
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
    run_image_ocr_flow(
        root,
        image_label,
        close_button,
        state,
        current_image,
        history,
        temp_files,
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

    root.title("tkinter / ttk Button Sample 00123")

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
        "<Control-V>",
        lambda event: handle_paste_image(
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
