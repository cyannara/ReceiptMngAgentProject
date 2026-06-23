# 📸 지능형 영수증 분석 & 사내 내규 심사 시스템 (Receipt Agent v1.0)

LangGraph 파이프라인과 OpenAI GPT-4o Vision 기술을 결합하여, 업로드된 영수증 이미지의 항목을 분류하고 사내 외근/출장 지출 내규(RAG) 준수 여부를 자동으로 심사하여 가계부 데이터 규격으로 정형화해주는 스마트 증빙 자동화 시스템입니다.

---

## ✨ 주요 기능 및 특징
- **Vision AI OCR 노드**: 오픈소스의 한계를 넘어 구겨지거나 흐릿한 실제 종이 영수증 사진까지 `gpt-4o` 시각 모델을 통해 라인과 테이블 구조를 완벽하게 텍스트로 판독합니다.
- **파이썬 기반 다인원 정산 로직**: 음료나 공기밥 등 소액 사이드 메뉴를 제외한 '주요 식사 메뉴'의 수량을 파이크 코드로 정확히 합산하여 동반 인원수(N)를 도출하고 1인당 비용을 계산합니다.
- **사내 지출 내규 RAG 검증**: 추출된 1인당 비용을 기반으로 사내 지급 규정(예: 외근 석식 1인당 20,000원 한도 등)을 참조하여 위반 여부를 동적으로 심사합니다.
- **정형 데이터 규격화 및 오늘 날짜 주입**: 기획서 DB 필드 규칙을 준수하여 상점 주소(`addr`), 연락처(`tel`), 그리고 정산 시점의 오늘 날짜(`reg_date`)를 안전하게 주입합니다.

---

## 🛠️ 개발 환경 및 필수 패키지 설치

본 프로젝트는 Anaconda 가상환경(`ml_env`) 환경에서 테스트 및 최적화되었습니다.

### 1. 가상환경 활성화 및 필수 라이브러리 설치
터미널 또는 Anaconda Prompt를 열고 프로젝트 폴더로 이동한 뒤 아래 명령어를 순서대로 실행하세요.

```bash
# 가상환경 활성화 (본인의 환경 이름으로 변경 가능)
conda activate ml_env

# LangGraph, OpenAI, Streamlit 등 핵심 패키지 설치
pip install langgraph langchain-core langchain-openai langchain-community langchain-text_splitters chroma4py
pip install streamlit pillow python-dotenv
