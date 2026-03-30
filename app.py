import io, json, time, os
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
    <title>AI 검수덕 - 정밀 심사 시스템 (v3.0 찐완성)</title>
    <style>
        body { font-family: 'Pretendard', sans-serif; text-align: center; background: #f8f9fa; padding: 20px; }
        .card { background: white; padding: 40px; border-radius: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); display: inline-block; width: 95%; max-width: 1000px; }
        #list { display: flex; flex-wrap: wrap; gap: 20px; justify-content: center; margin-top: 30px; }
        .box { border: 4px solid #e9ecef; border-radius: 15px; width: 140px; height: 140px; background: #fff; position: relative; transition: transform 0.2s; display: flex; align-items: center; justify-content: center; overflow: hidden; }
        .box img { width: 100%; height: 100%; object-fit: contain; padding: 5px; }
        #msg { background: #fff; border: 2px solid #dee2e6; padding: 20px; border-radius: 12px; margin-bottom: 30px; font-size: 1.1em; color: #495057; }
        .pass { border-color: #28a745 !important; background-color: #f1fbf3; }
        .fail { border-color: #dc3545 !important; background-color: #fdf3f4; }
        .reason-tag { position: absolute; bottom: 0; left: 0; right: 0; background: rgba(220, 53, 69, 0.9); color: white; font-size: 11px; padding: 5px; font-weight: bold; line-height: 1.2; word-break: break-all; }
        input[type="file"] { background: #fff; border: 2px dashed #adb5bd; padding: 20px; border-radius: 10px; width: 100%; cursor: pointer; }
    </style>
</head>
<body>
    <div class="card">
        <h2>🦆 스티커 정밀 검수 시스템 (최종버전)</h2>
        <div id="msg">공정하고 엄격한 심사를 위해 파일을 업로드해 주세요. (순차 분석 진행)</div>
        <input type="file" id="files" multiple accept="image/*">
        <div id="list"></div>
    </div>

    <script>
        document.getElementById('files').onchange = async (e) => {
            const files = e.target.files;
            if (files.length === 0) return;
            
            const list = document.getElementById('list');
            const msg = document.getElementById('msg');
            list.innerHTML = "";
            msg.innerHTML = "🔍 <b>공정 심사 가이드라인</b>에 따라 순차 분석을 시작합니다...<br><small>위반 콘텐츠는 반려 사유가 표시됩니다.</small>";

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
                        if (r.is_safe) {
                            boxes[i].classList.add('pass');
                        } else {
                            boxes[i].classList.add('fail');
                            const reasonDiv = document.createElement('div');
                            reasonDiv.className = 'reason-tag';
                            reasonDiv.innerText = r.reason;
                            boxes[i].appendChild(reasonDiv);
                        }
                    }
                });
                msg.innerHTML = "✅ <b>심사 완료</b><br>공정 가이드라인을 준수한 결과입니다. 빨간색은 수정이 필요합니다.";
            } catch (err) {
                msg.innerText = "❌ 서버 통신 중 치명적 오류가 발생했습니다.";
            }
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
            time.sleep(0.5)
            try:
                img = Image.open(io.BytesIO(f.read()))
                
                prompt = "당신은 스티커 심사 AI입니다. 결과는 반드시 JSON 형식으로만 답하세요. [조건] 1. 신체 노출/욕설 텍스트는 is_safe: false 2. 캐릭터/일상 밈은 is_safe: true. 예시: {'is_safe': true}"
                
                response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=[prompt, img]
                )
                
                # [수정] JSON 파싱 오류 방지를 위해 텍스트 정제
                clean_text = response.text.replace('```json', '').replace('```', '').strip()
                result = json.loads(clean_text)
                is_safe = result.get("is_safe", True)
                
                if is_safe:
                    res_list.append({"is_safe": True})
                else:
                    res_list.append({"is_safe": False, "reason": "가이드라인 위반"})
                
            except Exception as e:
                res_list.append({"is_safe": False, "reason": "검토 필요"})
                
        return jsonify(res_list)
        
    except Exception as e:
        return jsonify([{"is_safe": False, "reason": "에러"}]), 500

if __name__ == '__main__':
    # 렌더 서버 환경에 맞게 호스트 설정
    app.run(host='0.0.0.0', port=5000)
