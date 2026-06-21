import tkinter as tk
from tkinter import messagebox, filedialog
import yt_dlp
import threading
import os
import sys
# [자동 경로 탐색 코드]
# 윈도우에서 실행될 때 FFmpeg 경로를 프로그램이 스스로 찾게 만듭니다.
if getattr(sys, 'frozen', False):
    os.environ["PATH"] += os.pathsep + os.path.dirname(sys.executable)
# --- 음원 다운로드 로직 (안정화 순정 버전 - OAuth 제외) ---
def download_audio(urls, status_label, url_text, download_btn, save_dir):
    total = len(urls)
    download_btn.config(state=tk.DISABLED)
    save_path = save_dir.get()

    ydl_opts = {
        'format': 'bestaudio/best or worstvideo+bestaudio/best or best',
        'writethumbnail': True,
        'postprocessors': [
            {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            },
            {
                'key': 'FFmpegMetadata',
                'add_metadata': True,
            },
            # [해결책 1] webp 썸네일을 MP3에 들어갈 수 있도록 jpg로 강제 변환
            {
                'key': 'FFmpegThumbnailsConvertor',
                'format': 'jpg',
            },
            # 변환된 jpg를 MP3 앨범 커버로 삽입
            {
                'key': 'EmbedThumbnail',
            }
        ],
        # [해결책 2] 썸네일 합성 시 에러(Invalid argument)가 나지 않도록, 
        # 정규화 필터를 '오디오를 추출하는 단계'에만 핀포인트로 적용
        'postprocessor_args': {
            'FFmpegExtractAudio': ['-af', 'loudnorm=I=-14:LRA=11:TP=-1.5']
        },
        'outtmpl': os.path.join(save_path, '%(title)s.%(ext)s'),
        'noplaylist': True,
    }

    success_count = 0
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            for i, url in enumerate(urls, 1):
                status_label.after(0, lambda i=i: status_label.config(text=f"다운로드 중... ({i}/{total})", fg="#A0A0A0"))
                try:
                    ydl.download([url])
                    success_count += 1
                except Exception as e:
                    print(f"오류 발생 ({url}): {e}")
                    
        status_label.after(0, lambda: status_label.config(text=f"다운로드 완료! (성공: {success_count}/{total}개)", fg="#FFFFFF"))
        url_text.after(0, lambda: url_text.delete("1.0", tk.END))
        
    except Exception as e:
        status_label.after(0, lambda: status_label.config(text="오류 발생", fg="#FF6B6B"))
        url_text.after(0, lambda: messagebox.showerror("오류", f"처리 중 문제가 발생했습니다:\n{e}"))
    finally:
        download_btn.after(0, lambda: download_btn.config(state=tk.NORMAL))

def start_download_thread(url_text, status_label, download_btn, save_dir):
    raw_text = url_text.get("1.0", tk.END)
    urls = [url.strip() for url in raw_text.split('\n') if url.strip()]
    
    if not urls:
        messagebox.showwarning("입력 오류", "유튜브 URL 또는 검색어를 최소 1개 이상 입력해주세요.")
        return

    thread = threading.Thread(target=download_audio, args=(urls, status_label, url_text, download_btn, save_dir))
    thread.daemon = True
    thread.start()

# --- 멜론 Top 100 크롤링 (19금 회피 lyrics 패치 적용) ---
def fetch_melon_top100(status_label, url_text):
    status_label.config(text="멜론 차트를 읽어오는 중...", fg="#A0A0A0")
    def _fetch():
        try:
            import requests
            from bs4 import BeautifulSoup
            headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
            res = requests.get('https://www.melon.com/chart/index.htm', headers=headers)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, 'html.parser')
            songs = soup.find_all('tr', class_=['lst50', 'lst100'])
            
            # [수정됨] 공식 뮤비로 빠져서 오류나는 것을 막기 위해 'lyrics audio'를 기본으로 붙임
            search_queries = [f"ytsearch1:{song.find('div', class_='ellipsis rank02').find('a').text.strip()} {song.find('div', class_='ellipsis rank01').find('a').text.strip()} lyrics audio" for song in songs]
            
            url_text.after(0, lambda: url_text.insert(tk.END, '\n'.join(search_queries) + '\n'))
            status_label.after(0, lambda: status_label.config(text=f"멜론 Top {len(search_queries)} 불러오기 완료!", fg="#FFFFFF"))
        except Exception as e:
            status_label.after(0, lambda: status_label.config(text="멜론 파싱 실패", fg="#FF6B6B"))
    threading.Thread(target=_fetch, daemon=True).start()

# --- 재생목록 팝업창 로직 ---
def open_playlist_dialog(status_label, url_text, root):
    dialog = tk.Toplevel(root)
    dialog.title("재생목록 불러오기")
    dialog.geometry("400x140")
    dialog.configure(bg="#252525")
    dialog.resizable(False, False)
    dialog.transient(root)
    dialog.grab_set()

    lbl = tk.Label(dialog, text="유튜브 재생목록(Playlist) URL을 입력하세요:", bg="#252525", fg="#FFFFFF", font=("Helvetica", 11))
    lbl.pack(pady=(15, 5))

    entry_style = {"bg": "#383838", "fg": "#FFFFFF", "insertbackground": "#FFFFFF", "font": ("Helvetica", 10), "relief": "flat", "highlightthickness": 1, "highlightcolor": "#5A5A5A", "highlightbackground": "#383838"}
    pl_entry = tk.Entry(dialog, width=45, **entry_style)
    pl_entry.pack(pady=5, ipady=4)

    pl_entry.bind("<Command-v>", paste_event)
    pl_entry.bind("<Control-v>", paste_event)
    pl_entry.bind("<Button-3>", show_context_menu)
    pl_entry.bind("<Button-2>", show_context_menu)

    def submit(event=None):
        playlist_url = pl_entry.get().strip()
        dialog.destroy()
        if playlist_url:
            process_playlist(playlist_url, status_label, url_text)

    pl_entry.bind("<Return>", submit)
    btn = tk.Button(dialog, text="불러오기", command=submit, bg="#4A4A4A", fg="#FFFFFF", activebackground="#5A5A5A", activeforeground="#FFFFFF", font=("Helvetica", 10, "bold"), relief="flat", cursor="hand2")
    btn.pack(pady=(5, 10), ipadx=10, ipady=2)
    pl_entry.focus_set()

def process_playlist(playlist_url, status_label, url_text):
    status_label.config(text="재생목록 분석 중... 100곡 이상은 다소 소요됩니다.", fg="#A0A0A0")
    def _fetch():
        ydl_opts = {
            'extract_flat': 'in_playlist', 
            'quiet': True,
            'extractor_args': {'youtube': {'playlist_ajax': 'true'}}
            # OAuth 로직만 깔끔하게 제거됨
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(playlist_url, download=False)
            if 'entries' in info:
                urls = [entry['url'] for entry in info['entries'] if entry and entry.get('url')]
                url_text.after(0, lambda: url_text.insert(tk.END, '\n'.join(urls) + '\n'))
                status_label.after(0, lambda: status_label.config(text=f"재생목록에서 {len(urls)}곡 불러오기 완료!", fg="#FFFFFF"))
            else:
                status_label.after(0, lambda: status_label.config(text="재생목록을 찾을 수 없습니다.", fg="#FF6B6B"))
        except Exception as e:
            status_label.after(0, lambda: status_label.config(text="불러오기 실패", fg="#FF6B6B"))
            print(f"오류: {e}")

    threading.Thread(target=_fetch, daemon=True).start()

# --- 공용 붙여넣기 로직 ---
def paste_to_widget(widget):
    try:
        clipboard_data = widget.clipboard_get()
        widget.insert(tk.INSERT, clipboard_data)
    except tk.TclError: pass
    return "break"

def paste_event(event): return paste_to_widget(event.widget)
def show_context_menu(event):
    try:
        context_menu.post(event.x_root, event.y_root)
        context_menu.focus_widget = event.widget
    finally: pass
def menu_paste():
    if hasattr(context_menu, 'focus_widget'): paste_to_widget(context_menu.focus_widget)
def clear_text(): url_text.delete("1.0", tk.END)

# --- GUI 메인 화면 ---
root = tk.Tk()
root.title("mp3 추출 프로그램")
root.geometry("520x400") # 기능 버튼들을 위한 넉넉한 공간 확보
root.configure(bg="#252525")
root.resizable(False, False)

save_dir = tk.StringVar(value=os.getcwd())

context_menu = tk.Menu(root, tearoff=0, bg="#383838", fg="#FFFFFF", activebackground="#5A5A5A", activeforeground="#FFFFFF", borderwidth=0)
context_menu.add_command(label="붙여넣기 (Paste)", command=menu_paste)
context_menu.add_separator()
context_menu.add_command(label="전체 지우기 (Clear)", command=clear_text)

label_style = {"bg": "#252525", "fg": "#FFFFFF", "font": ("Helvetica", 13, "bold")}
text_style = {"bg": "#383838", "fg": "#FFFFFF", "insertbackground": "#FFFFFF", "font": ("Helvetica", 11), "relief": "flat", "highlightthickness": 1, "highlightcolor": "#5A5A5A", "highlightbackground": "#383838"}
button_style = {"bg": "#4A4A4A", "fg": "#FFFFFF", "activebackground": "#5A5A5A", "activeforeground": "#FFFFFF", "font": ("Helvetica", 10, "bold"), "relief": "flat", "cursor": "hand2"}

title_label = tk.Label(root, text="URL 또는 검색어를 한 줄에 하나씩 입력하세요", **label_style)
title_label.pack(pady=(15, 10))

dir_frame = tk.Frame(root, bg="#252525")
dir_frame.pack(fill="x", padx=30, pady=(0, 10))

dir_label = tk.Label(dir_frame, textvariable=save_dir, bg="#383838", fg="#A0A0A0", font=("Helvetica", 9), anchor="w", relief="flat", padx=10)
dir_label.pack(side="left", fill="x", expand=True, ipady=4)

dir_btn = tk.Button(dir_frame, text="📁 폴더 변경", command=lambda: save_dir.set(filedialog.askdirectory(initialdir=save_dir.get()) or save_dir.get()), **button_style)
dir_btn.pack(side="right", padx=(5, 0), ipadx=5, ipady=2)

btn_frame = tk.Frame(root, bg="#252525")
btn_frame.pack(fill="x", padx=30, pady=(0, 5))

clear_btn = tk.Button(btn_frame, text="🗑️ 지우기", command=clear_text, **button_style)
clear_btn.pack(side="left", ipadx=5, ipady=3)

# 살아돌아온 멜론과 재생목록 버튼!
melon_btn = tk.Button(btn_frame, text="🍈 멜론 Top100", command=lambda: fetch_melon_top100(status_label, url_text), **button_style)
melon_btn.pack(side="left", padx=10, ipadx=5, ipady=3)

playlist_btn = tk.Button(btn_frame, text="🎵 재생목록 불러오기", command=lambda: open_playlist_dialog(status_label, url_text, root), **button_style)
playlist_btn.pack(side="right", ipadx=5, ipady=3)

url_text = tk.Text(root, height=7, width=55, **text_style)
url_text.pack(pady=5)

url_text.bind("<Command-v>", paste_event) 
url_text.bind("<Control-v>", paste_event)
url_text.bind("<Button-3>", show_context_menu)
url_text.bind("<Button-2>", show_context_menu)

extract_btn_style = button_style.copy()
extract_btn_style["font"] = ("Helvetica", 11, "bold")
download_btn = tk.Button(root, text="일괄 추출하기", **extract_btn_style)
download_btn.config(command=lambda: start_download_thread(url_text, status_label, download_btn, save_dir))
download_btn.pack(pady=15, ipadx=20, ipady=8)

status_label = tk.Label(root, text="대기 중...", bg="#252525", fg="#A0A0A0", font=("Helvetica", 10))
status_label.pack(pady=0)

root.mainloop()