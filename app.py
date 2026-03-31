import io, json, time, os, traceback
from google import genai
from flask import Flask, request, jsonify, render_template_string
from PIL import Image

app = Flask(__name__)

# 환경변수에서 키 가져오기
api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>AI 검수덕 - 6시 마감 최종 승리본</title>
    <style>
        body { font-family: 'Pretendard', sans-serif; text-align: center; background: #f8f9fa; padding: 20px; }
        .card { background: white; padding: 40px; border-radius: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); display: inline-block; width: 95%; max-width: 1000px; }
        #list { display: flex; flex-wrap: wrap; gap: 20px; justify-content: center; margin-top: 30px; }
        .box { border: 4px solid #e9ecef; border-radius: 15px; width: 140px; height: 140px; background: #fff; position: relative; display: flex; align-items: center; justify-content: center; overflow: hidden; }
        .box img { width: 100%; height: 100%; object-fit: contain; padding: 5px; }
        #msg { background: #fff; border: 2px solid #dee2e6; padding: 20px; border-radius: 12px; margin-bottom: 30px; font-weight: bold; }
        .pass { border-color: #28a745 !important; background-color: #f1fbf3; }
        .fail { border-color: #dc3545 !important; background-color: #fdf3f4; }
        .reason-tag { position: absolute; bottom: 0; left: 0; right: 0; background: rgba(220, 53, 69, 0.9); color: white; font-size: 11px; padding: 5px; font-weight: bold; }
    </style>
</head>
<body>
    <div class="card">
        <h2>🦆 스티커 정밀 검수 시스템 (최종)</h2>
        <div id="msg">파일을 업로드하면 AI가 실시간으로 심사합니다.</div>
        <input type="file" id="files" multiple accept="image/*">
        <div id="list"></div>
    </div>
    <script>
        document.getElementById('files').onchange = async (e) => {
            const files = e.target.files;
            const list = document.getElementById('list');
            const msg = document.getElementById('msg');
            list.innerHTML = "";
            msg.innerHTML = "🔍 심사 중...";
            const formData = new FormData();
            for (let f of files) {
                formData.append('images', f);
                const div = document.createElement('div');
                div.className = 'box';
                const img = document.createElement('img');
                const reader = new FileReader();
                reader.onload = (ev) => { img.src = ev.target.result; };
                reader.readAsDataURL(f);
                div.appendChild(img);
                list.appendChild(div);
            }
            try {
                const res = await fetch('/analyze', { method: 'POST', body: formData });
                const results = await res.json();
                const boxes = document.querySelectorAll('.box');
                results.forEach((r, i) => {
                    if(boxes[i]) {
                        if (r.is_safe) boxes[i].classList.add('pass');
                        else {
                            boxes[i].classList.add('fail');
                            const tag = document.createElement('div');
                            tag.className = 'reason-tag';
                            tag.innerText = r.reason;
                            boxes[i].appendChild(tag);
                        }
                    }
                });
                msg.innerHTML = "✅ 심사 완료";
            } catch (err) { msg.innerText = "❌ 서버 에러"; }
        };
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        files = request.files.getlist('images')
        res_list = []
        for f in files:
            try:
                img = Image.open(io.BytesIO(f.read()))
                # [수정] 프롬프트에서 '검열하지 말라'고 강력하게 지시
                prompt = """
                당신은 스티커 심사관입니다. '어쩌라고' 같은 일상 문구는 무조건 합격시키세요.
                오직 명백한 성기 노출이나 심각한 패드립 욕설만 반려하세요.
                결과는 반드시 JSON으로만 답하세요: {"is_safe": true} 또는 {"is_safe": false, "reason": "위반"}
                """
                # [수정] 에러를 유발하는 safety_settings를 제거하고 기본값으로 실행
                response = client.models.generate_content(
                    model="gemini-1.5-flash",
                    contents=[prompt, img]
                )
                clean_txt = response.text.strip().replace('```json', '').replace('```', '')
                result = json.loads(clean_txt)
                res_list.append({"is_safe": result.get("is_safe", True), "reason": result.get("reason", "검토 필요")})
            except Exception as inner_e:
                print(traceback.format_exc())
                res_list.append({"is_safe": False, "reason": "검토 필요"})
        return jsonify(res_list)
    except Exception as e:
        print(traceback.format_exc())
        return jsonify([{"is_safe": False, "reason": "서버 장애"}]), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
