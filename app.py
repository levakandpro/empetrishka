from flask import Flask, request, send_file, jsonify, render_template, after_this_request
from threading import Semaphore
import yt_dlp
import os
import uuid
import time
import subprocess
import tempfile
import traceback
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)
limiter = Limiter(get_remote_address, app=app)

DOWNLOAD_FOLDER = os.path.join(app.root_path, 'downloads')
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'mp3', 'wav', 'flac', 'ogg', 'aac'}
download_limit = Semaphore(3)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/convert')
def convert_page():
    return render_template('convert.html')

@app.route('/download', methods=['POST'])
@limiter.limit("10 per minute")
def download_audio():
    url = request.form.get('url')
    if not url or not url.startswith('http'):
        return jsonify({'error': '❗ Неверная ссылка'}), 400

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
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
            final_filename = f"{safe_title}.mp3"
            filepath = os.path.splitext(ydl.prepare_filename(info))[0] + ".mp3"

        @after_this_request
        def remove_file(response):
            try: os.remove(filepath)
            except: pass
            download_limit.release()
            return response

        return send_file(
            filepath,
            mimetype='audio/mpeg',
            as_attachment=True,
            download_name=final_filename
        )
    except Exception as e:
        traceback.print_exc()
        download_limit.release()
        return jsonify({'error': f'❌ Ошибка: {str(e)}'}), 500

@app.route('/convert-audio', methods=['POST'])
def convert_audio():
    file = request.files.get('file')
    target_format = request.form.get('format', '').lower()

    if not file or not allowed_file(file.filename):
        return jsonify({'error': 'Файл или формат не указан или недопустим'}), 400

    try:
        original_filename = uuid.uuid4().hex + "_" + file.filename
        input_path = os.path.join(tempfile.gettempdir(), original_filename)
        file.save(input_path)

        output_filename = f"{uuid.uuid4().hex}.{target_format}"
        output_path = os.path.join(tempfile.gettempdir(), output_filename)

        subprocess.run(['ffmpeg', '-y', '-i', input_path, output_path], check=True)

        @after_this_request
        def cleanup(response):
            try:
                os.remove(input_path)
                os.remove(output_path)
            except: pass
            return response

        return send_file(output_path, as_attachment=True, download_name=output_filename)
    except Exception as e:
        return jsonify({'error': f'Ошибка конвертации: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
