import io, json, time
import google.generativeai as genai
from flask import Flask, request, jsonify, render_template_string
from PIL import Image

app = Flask(__name__)

# 1. API 설정
genai.configure(api_key="AIzaSyC15W7lzCBfHn7TV91Ls82aeLtishRD7n0")
model = genai.GenerativeModel('gemini-flash-lite-latest')
# 2. HTML 화면 (사유 표시 기능 추가!)
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
        
        /* 반려 사유를 보여주는 빨간 딱지 디자인 */
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
                            // 💡 빨간 테두리일 경우, 그 안에 반려 사유를 글자로 박아줍니다!
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
            time.sleep(1.0)
            try:
                img = Image.open(io.BytesIO(f.read()))
                
                prompt = """
                당신은 스티커 자동 심사 AI입니다. 결과는 반드시 JSON 형식으로만 답하세요.
                
                [반려 조건] - 아래 해당하면 {"is_safe": false}
                1. 명백하게 야한 사진 (사람의 신체 노출 등)
                2. 심한 욕설이 적힌 텍스트
                
                [합격 조건] - 위가 아니면 무조건 {"is_safe": true}
                - 오리, 햄스터 등 캐릭터, 일상 밈(ㅋㅋ, 가즈아 등)
                """
                
                response = model.generate_content(
                    [prompt, img],
                    generation_config={"response_mime_type": "application/json"}
                    # 주의: 구글 자체 필터를 끄지 않고 기본값으로 둡니다. (누드 사진에서 확실하게 에러를 뱉도록 유도)
                )
                
                result = json.loads(response.text)
                is_safe = result.get("is_safe", True)
                
                if is_safe:
                    res_list.append({"is_safe": True})
                else:
                    # AI가 얌전하게 "이거 가이드라인 위반이야"라고 false를 줬을 때
                    res_list.append({"is_safe": False, "reason": "가이드라인 위반"})
                
            except Exception as e:
                error_msg = str(e).lower()
                
                # 💡 핵심 1: 구글 안전 필터가 발동해서 에러를 뿜었을 때 (누드 사진 등)
                if "blocked" in error_msg or "empty" in error_msg or "safety" in error_msg:
                    print("🚨 [안전 필터 작동] 차단됨!")
                    res_list.append({"is_safe": False, "reason": "콘텐츠를 확인해주세요 (검열)"})
                    
                # 💡 핵심 2: 그 외의 진짜 이상한 에러들 (할당량 초과, 파싱 에러 등)
                else:
                    print(f"⚠️ [시스템 에러] {error_msg}")
                    # 화면에 보여주기 위해 에러 메시지를 짧게 잘라서 보냄
                    short_error = str(e)[:25] + "..."
                    res_list.append({"is_safe": False, "reason": f"오류: {short_error}"})
                
        return jsonify(res_list)
        
    except Exception as e:
        return jsonify([{"is_safe": False, "reason": "서버 완전 뻗음"}] * len(request.files.getlist('images')))

if __name__ == '__main__':
    app.run(debug=True, port=5000)