import os
import tempfile
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

try:
    from ocr.receipt_workflow import langgraph_app
except ModuleNotFoundError:
    from backend.ocr.receipt_workflow import langgraph_app

load_dotenv()

app = FastAPI(title="Smart Receipt Agent Backend", version="1.0")

# 외부 교차 출처 스크립트(CORS) 허용 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


# ==========================================
# REST API 엔드포인트 구현
# ==========================================
@app.post("/api/analyze-receipt")
async def analyze_receipt_api(request: Request, file: UploadFile = File(...)):
    try:
        # 1. 파일 스트림을 수신하여 안전하게 임시 파일로 격리 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
            temp_file.write(await file.read())
            temp_file_path = temp_file.name
            
        # 2. LangGraph 수동 호출 설정 빌드
        config = {"configurable": {"thread_id": "fastapi_agent_runtime_session"}}
        initial_state = {
            "messages": [HumanMessage(content="FastAPI 백엔드 수신 엔진 가동")],
            "image_path": temp_file_path,
            "ocr_provider": request.query_params.get("ocr_provider", "gpt"),
            "notion_sync_status": "pending"
        }
        
        # 3. 파이썬 백엔드 스레드에서 랭그래프 순차 컴파일 실행
        langgraph_app.invoke(initial_state, config=config)
        
        # 4. 최종 누적 결과 적재 상태 반환
        final_values = langgraph_app.get_state(config).values
        
        # 임시 이미지 파일 자원 삭제
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            
        return {"status": "success", "data": final_values}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ADIM code by Kate 20260625

# 1. 프론트엔드 요청 데이터 검증을 위한 Pydantic 모델
class AdminDashboardRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    category: Optional[str] = None

# 2. 어드민 대시보드 데이터 조회 엔드포인트 신설
@app.post("/api/admin/dashboard")
async def get_admin_dashboard_data(payload: AdminDashboardRequest):
    try:
        # save_local_db에 추가한 공용 함수 호출
        try:
            from backend.db.save_local_db import load_dashboard_data_shared
        except Exception:
            from db.save_local_db import load_dashboard_data_shared
        
        result_data = load_dashboard_data_shared(
            db_target=None,
            start_date=payload.start_date,
            end_date=payload.end_date,
            category=payload.category
        )
        return {"status": "success", "data": result_data}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"백엔드 대시보드 쿼리 실패: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
