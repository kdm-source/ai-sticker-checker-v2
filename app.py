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
    <title>AI OGQ</title>
    <style>
    body { font-family: 'Pretendard', sans-serif; text-align: center; background: #f8f9fa; padding: 20px; }
    .card { background: white; padding: 40px; border-radius: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); display: inline-block; width: 95%; max-width: 1000px; }
    #list { display: flex; flex-wrap: wrap; gap: 20px; justify-content: center; margin-top: 30px; }
    
    /* 텍스트가 들어가야 하므로 박스 크기를 세로로 키웠습니다 */
    .box { border: 4px solid #e9ecef; border-radius: 15px; width: 200px; min-height: 280px; background: #fff; position: relative; display: flex; flex-direction: column; align-items: center; overflow: hidden; transition: 0.3s; }
    .box img { width: 100%; height: 150px; object-fit: contain; padding: 10px; background: #fafafa; }
    
    #msg { background: #fff; border: 2px solid #dee2e6; padding: 20px; border-radius: 12px; margin-bottom: 30px; font-weight: bold; }
    
    /* 상태별 테두리 색상 */
    .pass { border-color: #28a745 !important; }
    .fail { border-color: #dc3545 !important; }
    
    /* 상세 사유가 들어갈 하단 영역 */
    .info-area { padding: 12px; font-size: 12px; text-align: left; line-height: 1.4; flex-grow: 1; width: 100%; border-top: 1px solid #eee; background: #fff; }
    .pass .info-area { background-color: #f1fbf3; color: #155724; }
    .fail .info-area { background-color: #fdf3f4; color: #721c24; }
    
    .tip-text { display: block; margin-top: 8px; font-size: 11px; color: #666; border-top: 1px dashed #ccc; padding-top: 5px; }
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
                        const info = document.createElement('div');
                        info.className = 'info-area';
                        
                        if (r.is_safe) {
                            boxes[i].classList.add('pass');
                            info.innerHTML = `<b>✅ 승인 사유</b><br>${r.reason}<br><span class="tip-text">💡 팁: ${r.tip}</span>`;
                        } else {
                            boxes[i].classList.add('fail');
                            info.innerHTML = `<b>❌ 반려 사유</b><br>${r.reason}<br><span class="tip-text">💡 수정 제안: ${r.tip}</span>`;
                        }
                        boxes[i].appendChild(info);
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
                # 1. 이미지 처리
                img = Image.open(io.BytesIO(f.read()))
                img.thumbnail((512, 512)) 

                # 2. 프롬프트 세팅
                prompt = """
                당신은 글로벌 메신저의 '스티커 콘텐츠 전문 심사관'입니다. 
                제공된 이미지를 분석하여 다음 가이드라인에 따라 심사평을 작성하세요.

                [심사 원칙]
                - 긍정적 검토: 창작의 자유를 존중하며, 일상적인 유머나 문구(예: 어쩌라고)는 적극 수용합니다.
                - 엄격한 금기: 과도한 신체 노출, 성적인 암시, 특정 계층 비하, 폭력적인 묘사만 제한합니다.

                [응답 항목]
                1. is_safe: 승인 여부 (true/false)
                2. reason: [승인 시] 이미지의 긍정적인 요소 설명 / [반려 시] 구체적인 규정 위반 사유 설명
                3. tip: [공통] 향후 창작 시 참고할 만한 구체적인 개선 아이디어나 제안

                [출력 형식 - JSON]
                {
                  "is_safe": true/false,
                  "reason": "이미지의 구도와 문구가 조화로우며 사용자들에게 즐거움을 줄 수 있는 일상적 표현입니다.",
                  "tip": "캐릭터의 표정을 조금 더 다양하게 구성하면 시리즈물로서의 매력이 더 높아질 것 같습니다."
                }
                """

                # 3. 모델 호출 (2.5으로 고정)
                response = client.models.generate_content(
                    model="gemini-2.5-flash", 
                    contents=[prompt, img]
                )

                # 4. JSON 파싱
                clean_txt = response.text.strip().replace('```json', '').replace('```', '')
                result = json.loads(clean_txt)
                res_list.append({
                    "is_safe": result.get("is_safe", True), 
                    "reason": result.get("reason", "검토 필요")
                })

            except Exception as inner_e:
                # 할당량 초과나 모델 에러 시 로그를 찍고 리스트에 추가
                print(f"이미지 처리 중 개별 에러: {inner_e}")
                res_list.append({"is_safe": False, "reason": "할당량 초과(대기 필요)"})
        
        return jsonify(res_list)

    except Exception as e:
        print(f"전체 시스템 에러: {traceback.format_exc()}")
        return jsonify([{"is_safe": False, "reason": "서버 장애"}]), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
