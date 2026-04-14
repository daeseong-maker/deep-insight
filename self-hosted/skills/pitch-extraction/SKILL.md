---
name: pitch-extraction
description: >
  ShortFlow 기획안 PDF에서 콘텐츠 메타데이터를 자동 추출하는 스킬.
  사용자가 "기획안 읽어줘", "PDF에서 정보 뽑아줘", "메타데이터 추출해줘" 등의 요청을 하면 이 스킬을 사용하세요.
license: MIT
allowed-tools:
  - bash_tool
  - file_read
  - file_write
---

# Pitch Extraction Skill

이 스킬은 한국어 기획안 PDF에서 9개의 메타데이터 필드를 자동으로 추출합니다.

## 사용 방법

사용자가 기획안 PDF 파일 경로를 제공하면, 다음 Python 코드를 실행하세요:

```python
import sys
sys.path.insert(0, 'skills/pitch-extraction')
from pitch_extractor import PitchExtractor
import json

# PDF 경로 (사용자가 제공한 경로 사용)
pdf_path = "사용자가_제공한_경로.pdf"

# 추출 실행
extractor = PitchExtractor()
result = extractor.extract(pdf_path)

# 결과 출력
output = {
    "extractedAt": result.extracted_at,
    "parsingMethod": result.parsing_method,
    "fields": {
        "title": result.fields.title,
        "logline": result.fields.logline,
        "synopsis": result.fields.synopsis,
        "characterDescription": result.fields.character_description,
        "episodes": result.fields.episodes,
        "runtime": result.fields.runtime,
        "genre": result.fields.genre,
        "productionYear": result.fields.production_year,
        "productionStatus": result.fields.production_status
    },
    "confidence": result.confidence,
    "missingFields": result.missing_fields
}

print(json.dumps(output, ensure_ascii=False, indent=2))
```

## 추출되는 필드

1. **title** (제목): 작품명
2. **logline** (로그라인): 한 줄 소개
3. **synopsis** (시놉시스): 줄거리
4. **characterDescription** (등장인물): 캐릭터 설명
5. **episodes** (회차): 총 몇 화
6. **runtime** (러닝타임): 회당 몇 분
7. **genre** (장르): 장르 (배열)
8. **productionYear** (제작년도): 제작 연도
9. **productionStatus** (제작상태): 기획중/제작중/완성

## 신뢰도 레벨

각 필드는 신뢰도 레벨을 가집니다:
- **high**: 명확한 라벨로 추출됨
- **medium**: 패턴 매칭으로 추출됨
- **low**: 추출 실패
- **inferred**: 다른 필드에서 추론됨

## 예시

사용자 요청: "기획안 PDF에서 메타데이터 추출해줘. 파일은 ./data/pitch/마피아킹_기획안_20260119.pdf"

응답:
```json
{
  "extractedAt": "2026-04-13T10:30:00Z",
  "parsingMethod": "opendataloader",
  "fields": {
    "title": "마피아킹",
    "logline": "마피아 세계의 왕이 되는 이야기",
    "synopsis": "...",
    "characterDescription": "...",
    "episodes": 57,
    "runtime": 3,
    "genre": ["액션", "범죄"],
    "productionYear": 2026,
    "productionStatus": "완성"
  },
  "confidence": {
    "title": "high",
    "logline": "high",
    ...
  },
  "missingFields": []
}
```
