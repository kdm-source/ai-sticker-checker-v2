import io, json, time, os, traceback
from google import genai
from google.genai import types  # 안전 설정을 위해 추가
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
        .box { border: 4px solid #e9ecef; border-radius: 15px; width: 140px; height: 140px; background: #fff; position: relative; display: flex; align-items: center; justify-content: center; overflow: hidden; transition: transform 0.2s; }
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
                
                # [강력 프롬프트] AI에게 가이드라인 주입
                prompt = """
                당신은 스티커 가이드라인 심사관입니다. 다음 기준에 따라 JSON으로만 답하세요:
                1. [반려] 노출(성기, 엉덩이, 가슴 등), 성적인 암시, 심한 욕설(시발, 미친 등) -> {"is_safe": false, "reason": "검토 필요"}
                2. [합격] 귀여운 동물, 캐릭터, 일상 문구, 유머 -> {"is_safe": true}
                답변은 마크다운 없이 순수 JSON만 출력하세요.
                """
                
                # [수정] 자체 검열 완화 설정 추가
                response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=[prompt, img],
                    config=types.GenerateContentConfig(
                        safety_settings=[
                            types.SafetySetting(category="HATE_SPEECH", threshold="BLOCK_NONE"),
                            types.SafetySetting(category="HARASSMENT", threshold="BLOCK_NONE"),
                            types.SafetySetting(category="SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                            types.SafetySetting(category="DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
                        ]
                    )
                )
                
                # 텍스트 정제 (마크다운 제거)
                clean_txt = response.text.strip().replace('```json', '').replace('```', '')
                result = json.loads(clean_txt)
                
                res_list.append({
                    "is_safe": result.get("is_safe", True),
                    "reason": result.get("reason", "검토 필요")
                })
                
            except Exception as inner_e:
                print("--- 개별 이미지 분석 에러 ---")
                print(traceback.format_exc())
                # 에러 발생 시에도 '검토 필요'로 표시
                res_list.append({"is_safe": False, "reason": "검토 필요"})
                
        return jsonify(res_list)
        
    except Exception as e:
        print("--- 전체 프로세스 치명적 에러 ---")
        print(traceback.format_exc())
        return jsonify([{"is_safe": False, "reason": "서버 장애"}]), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
