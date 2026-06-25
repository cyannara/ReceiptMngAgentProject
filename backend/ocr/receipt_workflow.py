import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Dict, List, Literal, TypedDict

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

try:
    from app.services.rag_service import PolicyRagService
except ModuleNotFoundError:
    from services.rag_service import PolicyRagService

try:
    from .ocr_service import run_ocr
except ImportError:
    from ocr.ocr_service import run_ocr


class ReceiptAgentState(TypedDict):
    messages: Annotated[list, add_messages]
    ocr_provider: str
    id: str
    user_id: str
    spent_at: str
    merchant: str
    amount: int
    payment_method: str
    category: str
    memo: str
    source: str
    budget_status: str
    notion_sync_status: str
    addr: str
    tel: str
    reg_date: str
    items: List[Dict[str, Any]]
    detected_people_count: int
    per_person_amount: int
    image_path: str
    ocr_raw_text: str
    rag_violation_report: str
    category_confidence: float
    category_reason: str
    policy_category: str
    category_matched_rules: List[str]
    payment_status: str
    payment_reason: str


POLICY_RAG_SERVICE: PolicyRagService | None = None


def get_policy_rag_service() -> PolicyRagService:
    global POLICY_RAG_SERVICE
    if POLICY_RAG_SERVICE is None:
        POLICY_RAG_SERVICE = PolicyRagService()
    return POLICY_RAG_SERVICE


def upload_receipt_node(state: ReceiptAgentState):
    path = state.get("image_path", "").strip()
    if not path or not os.path.exists(path):
        return {"source": "image", "id": "error_id"}
    return {"source": "image", "id": f"api_fixed_{int(os.path.getmtime(path))}"}


def ocr_process_node(state: ReceiptAgentState):
    path = state.get("image_path")
    try:
        provider = state.get("ocr_provider") or os.getenv("OCR_PROVIDER", "gpt")
        ocr_text = run_ocr(path, provider=provider)
        print(f"[OCR Process] 추출된 텍스트 길이: {len(ocr_text)}")
        return {"ocr_raw_text": ocr_text}
    except Exception as e:
        print(f"[OCR Process] OCR 처리 중 오류 발생: {e}")
        return {"ocr_raw_text": f"OCR 에러: {e}"}


def analyze_expenditure_node(state: ReceiptAgentState):
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)
    parsing_prompt = f"""영수증 텍스트를 파싱하여 규정된 JSON 구조로만 반환하세요.
    OCR 원문: {state['ocr_raw_text']}
    JSON 양식:
    {{
      "spent_at": "YYYY-MM-DD", "merchant": "상점명", "addr": "주소", "tel": "전화번호", "amount": 총합금액(숫자),
      "payment_method": "결제수단", "items": [{{"name": "품목명", "count": 수량(숫자), "total": 금액(숫자)}}]
    }}
    """
    try:
        response = llm.invoke([HumanMessage(content=parsing_prompt)], response_format={"type": "json_object"})
        result = json.loads(response.content)
        total_amount = result.get("amount", 0)
        parsed_items = result.get("items", [])

        people_count = 0
        for item in parsed_items:
            item_name = item.get("name", "")
            item_count = item.get("count", 1)
            exclude_keywords = ["음료", "콜라", "사이다", "소주", "맥주", "공기밥", "공깃밥", "사리"]
            if not any(keyword in item_name for keyword in exclude_keywords):
                people_count += item_count
        if people_count <= 0:
            people_count = 1
        per_person = int(total_amount / people_count)

        return {
            "spent_at": result.get("spent_at"),
            "merchant": result.get("merchant"),
            "addr": result.get("addr", ""),
            "tel": result.get("tel", ""),
            "reg_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "amount": total_amount,
            "payment_method": result.get("payment_method", ""),
            "category": "식비/외근",
            "items": parsed_items,
            "detected_people_count": people_count,
            "per_person_amount": per_person,
            "memo": f"Vision OCR 기반 파이썬 로직 정밀 연산 / 총 {people_count}명 식사",
        }
    except Exception:
        return {"merchant": "파싱에러", "amount": 0, "detected_people_count": 1, "per_person_amount": 0}


def policy_rag_node(state: ReceiptAgentState):
    try:
        item_names = [
            item.get("name", str(item)) if isinstance(item, dict) else str(item)
            for item in state.get("items", [])
        ]
        result = get_policy_rag_service().classify(
            receipt_text=state.get("ocr_raw_text", ""),
            store_name=state.get("merchant", ""),
            items=item_names,
            memo=state.get("memo", ""),
            per_person_amount=state.get("per_person_amount", 0),
        )
        print(f"[RAG 분류 결과] 카테고리: {result.category}, 신뢰도: {result.confidence}, 지급여부: {result.payment_status}")
    except Exception as e:
        return {
            "category": state.get("category", "기타"),
            "category_confidence": 0.0,
            "category_reason": "RAG 카테고리 분류에 실패했습니다.",
            "policy_category": "기타",
            "category_matched_rules": [],
            "payment_status": "검토 필요",
            "payment_reason": "RAG 분류 실패로 지급여부를 자동 판단하지 못했습니다.",
            "rag_violation_report": f"RAG 분류 실패: {e}",
        }

    return {
        "category": result.category,
        "category_confidence": result.confidence,
        "category_reason": result.reason,
        "policy_category": result.policy_category,
        "category_matched_rules": result.matched_rules,
        "payment_status": result.payment_status,
        "payment_reason": result.payment_reason,
        "rag_violation_report": result.report,
    }


def evaluate_budget_node(state: ReceiptAgentState):
    status = "주의" if "위반" in state.get("rag_violation_report", "") else "정상"
    return {"budget_status": status}


def save_db_node(state: ReceiptAgentState):
    project_root = Path(__file__).resolve().parents[1]
    backend_dir = Path(__file__).resolve().parent
    for path in (project_root, backend_dir):
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)

    try:
        from backend.db.save_local_db import save_local_db
    except Exception:
        try:
            from db.save_local_db import save_local_db
        except Exception as fallback_error:
            print(f"[DB 로그] save_local_db import 실패: {fallback_error}")
            return {"saved_local_db": False, "db_error": str(fallback_error)}

    expense_data = {
        "user_id": state.get("user_id", "unknown-user"),
        "spent_at": state.get("spent_at"),
        "merchant": state.get("merchant"),
        "amount": state.get("amount", 0),
        "payment_method": state.get("payment_method", ""),
        "category": state.get("category", "미분류"),
        "memo": state.get("memo", ""),
        "source": state.get("source", "image"),
        "budget_status": state.get("budget_status", "정상"),
        "notion_sync_status": state.get("notion_sync_status", "pending"),
        "addr": state.get("addr", ""),
        "tel": state.get("tel", ""),
        "reg_date": state.get("reg_date", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        "items": state.get("items", []),
        "detected_people_count": state.get("detected_people_count", 1),
        "per_person_amount": state.get("per_person_amount", 0),
        "image_path": state.get("image_path", ""),
        "raw_text": state.get("ocr_raw_text", ""),
        "ocr_raw_text": state.get("ocr_raw_text", ""),
        "rag_violation_report": state.get("rag_violation_report", ""),
        "category_confidence": state.get("category_confidence", 0.0),
        "category_reason": state.get("category_reason", ""),
        "category_matched_rules": state.get("category_matched_rules", []),
    }

    save_result = save_local_db(expense_data)
    print(
        f"[DB 로그] 저장결과={save_result.get('saved_local_db')} "
        f"expense_id={save_result.get('expense_id')} "
        f"error={save_result.get('db_error')} "
        f"상점명={expense_data.get('merchant')} 금액={expense_data.get('amount')}"
    )

    return {"db_save_result": save_result}


def record_notion_node(state: ReceiptAgentState):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    notion_dir = os.path.join(current_dir, "notion")
    if notion_dir not in sys.path:
        sys.path.insert(0, notion_dir)

    current_dir2 = os.path.dirname(os.path.abspath(__file__))
    root_dir2 = os.path.dirname(os.path.dirname(current_dir2))
    expense_graph_path = os.path.join(root_dir2, "ExpenseGraph")

    if expense_graph_path not in sys.path:
        sys.path.append(expense_graph_path)

    from notion.notion_record_agent import record_expense_to_notion
    from notion.notion_models import ExpenseRecord

    expense_record = ExpenseRecord(
        id=state.get("id", "EXP-UNKNOWN"),
        user_id=state.get("user_id", "unknown-user"),
        amount=state.get("amount", 0),
        category=state.get("category", "미분류"),
        payment_method=state.get("payment_method", "미지정"),
        merchant=state.get("merchant", "알 수 없음"),
        memo=state.get("memo", ""),
        source="image_upload",
        budget_status=state.get("budget_status", "평가 보류"),
        notion_sync_status="pending",
        addr=state.get("addr", "정보 없음"),
        tell=state.get("tell", "정보 없음"),
    )

    try:
        result = record_expense_to_notion(expense_record)
        if result.ok:
            print(f"✅ 노션 기록 성공! Page URL: {result.page_url}")
            return {"notion_sync_status": "success"}
        print(f"❌ 노션 기록 실패(Dry-run 또는 에러): {result.message}")
        return {"notion_sync_status": "failed"}
    except Exception as e:
        print(f"❌ 노션 연동 노드 에러 발생: {str(e)}")
        return {"notion_sync_status": "failed"}


def route_after_budget(state: ReceiptAgentState) -> Literal["to_notion", "to_end"]:
    return "to_notion"


def build_receipt_workflow():
    workflow = StateGraph(ReceiptAgentState)
    workflow.add_node("upload_receipt", upload_receipt_node)
    workflow.add_node("ocr_process", ocr_process_node)
    workflow.add_node("analyze_expenditure", analyze_expenditure_node)
    workflow.add_node("policy_rag", policy_rag_node)
    workflow.add_node("evaluate_budget", evaluate_budget_node)
    workflow.add_node("save_db", save_db_node)
    workflow.add_node("record_notion", record_notion_node)

    workflow.add_edge(START, "upload_receipt")
    workflow.add_edge("upload_receipt", "ocr_process")
    workflow.add_edge("ocr_process", "analyze_expenditure")
    workflow.add_edge("analyze_expenditure", "policy_rag")
    workflow.add_edge("policy_rag", "evaluate_budget")
    workflow.add_edge("evaluate_budget", "save_db")
    workflow.add_conditional_edges("save_db", route_after_budget, {"to_notion": "record_notion", "to_end": END})
    workflow.add_edge("record_notion", END)

    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)


langgraph_app = build_receipt_workflow()

__all__ = ["ReceiptAgentState", "build_receipt_workflow", "langgraph_app"]
