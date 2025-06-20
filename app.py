from flask import Flask, request, send_file, jsonify, render_template, Response
from pydub import AudioSegment
from threading import Semaphore
import yt_dlp
import os
import uuid
import threading
import time
import traceback
from urllib.parse import urlparse
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)
limiter = Limiter(get_remote_address, app=app)

DOWNLOAD_FOLDER = os.path.join(app.root_path, 'downloads')
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
app.config['DOWNLOAD_FOLDER'] = DOWNLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20 MB

COUNTER_FILE = 'counter.txt'
LOG_FILE = 'log.txt'
ERROR_LOG_FILE = 'errors.log'
ALLOWED_EXTENSIONS = {'mp3', 'wav', 'flac', 'ogg', 'aac'}

download_limit = Semaphore(3)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_download_count():
    if not os.path.exists(COUNTER_FILE):
        with open(COUNTER_FILE, 'w') as f:
            f.write('0')
        return 0
    with open(COUNTER_FILE, 'r') as f:
        return int(f.read().strip())

def increment_download_count():
    count = get_download_count() + 1
    with open(COUNTER_FILE, 'w') as f:
        f.write(str(count))
    return count

def log_error_to_email(error_text):
    pass  # временно отключено отправка email

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
@limiter.limit("10 per minute")
def download_audio():
    from flask import after_this_request  # ✅ локальный импорт

    url = request.form.get('url')
    if not url or not url.startswith('http'):
        return jsonify({'error': '❗ Неверная ссылка'}), 400

    parsed = urlparse(url)
    platform = parsed.hostname.replace("www.", "") if parsed.hostname else "unknown"
    uid = uuid.uuid4().hex
    output_template = os.path.join(DOWNLOAD_FOLDER, f"{uid}.%(ext)s")

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_template,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
        'noplaylist': True,
    }

    try:
        acquired = download_limit.acquire(timeout=15)
        if not acquired:
            return jsonify({'error': '⚠️ Слишком много одновременных загрузок'}), 429

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'audio')
            platform = info.get('extractor_key', platform)

            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
            final_filename = f"empetrishka - {safe_title}.mp3"
            temp_filepath = os.path.splitext(ydl.prepare_filename(info))[0] + ".mp3"

        increment_download_count()
        with open(LOG_FILE, "a", encoding="utf-8") as log:
            log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {platform} | {title} | {url}\n")

        @after_this_request
        def remove_file(response):
            try:
                os.remove(temp_filepath)
            except Exception:
                pass
            download_limit.release()
            return response

        return send_file(
            temp_filepath,
            mimetype='audio/mpeg',
            as_attachment=True,
            download_name=final_filename
        )

    except Exception as e:
        error_text = traceback.format_exc()
        with open(ERROR_LOG_FILE, "a") as log:
            log.write(error_text)
        log_error_to_email(error_text)
        download_limit.release()
        return jsonify({'error': f'❌ Ошибка: {str(e)}'}), 500

@app.route('/convert-audio', methods=['POST'])
@limiter.limit("15 per minute")
def convert_audio():
    from flask import after_this_request  # ✅ локальный импорт

    file = request.files.get('audio')
    target_format = request.form.get('format', 'mp3')
    quality = request.form.get('quality', 'medium')
    bitrate_manual = request.form.get('bitrate')

    if not file or not allowed_file(file.filename):
        return "Недопустимый или отсутствующий файл", 400

    filename = uuid.uuid4().hex
    input_path = os.path.join(DOWNLOAD_FOLDER, f"{filename}_in")
    output_path = os.path.join(DOWNLOAD_FOLDER, f"{filename}_out.{target_format}")

    file.save(input_path)

    try:
        audio = AudioSegment.from_file(input_path)

        if quality == 'manual' and bitrate_manual:
            bitrate = f"{bitrate_manual}k"
        elif quality == 'high':
            bitrate = "320k"
        elif quality == 'low':
            bitrate = "128k"
        else:
            bitrate = "192k"

        audio.export(output_path, format=target_format, bitrate=bitrate)
        os.remove(input_path)

        @after_this_request
        def remove_file(response):
            try:
                os.remove(output_path)
            except:
                pass
            return response

        return send_file(
            output_path,
            as_attachment=True,
            download_name=f"converted.{target_format}",
            mimetype=f"audio/{target_format}"
        )
    except Exception as e:
        error_text = traceback.format_exc()
        with open(ERROR_LOG_FILE, "a") as log:
            log.write(error_text)
        log_error_to_email(error_text)
        return f"Ошибка конвертации: {str(e)}", 500

@app.route('/convert')
def convert_page():
    return render_template('convert.html')

@app.route('/mobile')
def mobile_version():
    return render_template('mobile.html')

@app.route('/stats')
def stats():
    count = get_download_count()
    return f'Скачиваний: {count}'

@app.route('/download-count')
def download_count():
    return str(get_download_count())

@app.route('/robots.txt')
def robots_txt():
    return Response("User-agent: *\nAllow: /\nSitemap: https://empetrishka.app/sitemap.xml", mimetype='text/plain')

@app.route('/sitemap.xml')
def sitemap():
    return send_file("static/sitemap.xml")

@app.route('/logs')
def view_logs():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            return f"<pre>{f.read()}</pre>"
    return "Нет логов"

@app.route('/errors')
def view_errors():
    if os.path.exists(ERROR_LOG_FILE):
        with open(ERROR_LOG_FILE, 'r', encoding='utf-8') as f:
            return f"<pre>{f.read()}</pre>"
    return "Нет ошибок"

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'public, max-age=31536000'
    return response

def cleanup_old_files():
    while True:
        now = time.time()
        for filename in os.listdir(DOWNLOAD_FOLDER):
            if filename.endswith(('.mp3', '.wav', '.flac', '.ogg', '.aac')):
                path = os.path.join(DOWNLOAD_FOLDER, filename)
                if os.path.isfile(path) and now - os.path.getmtime(path) > 600:
                    try:
                        os.remove(path)
                    except:
                        pass
        time.sleep(300)

threading.Thread(target=cleanup_old_files, daemon=True).start()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
