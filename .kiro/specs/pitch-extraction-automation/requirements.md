# Requirements Document

## Introduction

The pitch extraction automation feature enables ShortFlow production companies to automatically extract content metadata from Korean pitch PDFs, eliminating manual data entry during content registration. The system uses a two-stage parsing strategy (opendataloader-pdf followed by Upstage Document Parse API fallback) to extract 9 metadata fields and return structured JSON with confidence levels.

## Glossary

- **Pitch_Extractor**: The system component responsible for extracting metadata from pitch PDFs
- **PDF_Parser**: The component that converts PDF files to text using opendataloader-pdf or Upstage Document Parse API
- **Metadata_Validator**: The component that validates extracted fields and assigns confidence levels
- **Field_Extractor**: The component that identifies and extracts specific metadata fields from parsed text
- **Fallback_Detector**: The component that determines when to use Upstage Document Parse API
- **Production_Company**: The user role that uploads pitch PDFs and receives extracted metadata
- **Pitch_PDF**: A PDF document containing Korean content metadata (title, logline, synopsis, etc.)
- **Confidence_Level**: A quality indicator for extracted fields (high, medium, low, inferred)
- **Upstage_Credit**: A billable unit consumed when using Upstage Document Parse API

## Requirements

### Requirement 1: PDF Parsing with Two-Stage Strategy

**User Story:** As a Production_Company, I want the system to parse my pitch PDF efficiently, so that I minimize API costs while ensuring successful text extraction.

#### Acceptance Criteria

1. WHEN a Pitch_PDF is uploaded, THE PDF_Parser SHALL attempt text extraction using opendataloader-pdf first
2. WHEN opendataloader-pdf extraction completes, THE Fallback_Detector SHALL evaluate the extracted text quality
3. IF extracted text is less than 100 characters, THEN THE Fallback_Detector SHALL trigger Upstage Document Parse API fallback
4. IF Korean character ratio is less than 10% of total text, THEN THE Fallback_Detector SHALL trigger Upstage Document Parse API fallback
5. IF average characters per page is less than 50, THEN THE Fallback_Detector SHALL trigger Upstage Document Parse API fallback
6. WHEN Upstage Document Parse API is triggered, THE PDF_Parser SHALL include OCR capability for image-based content
7. THE PDF_Parser SHALL return the parsing method used (opendataloader or upstage_dp) in the response

### Requirement 2: Metadata Field Extraction

**User Story:** As a Production_Company, I want the system to extract all 9 required metadata fields from my pitch PDF, so that I can pre-fill the registration form.

#### Acceptance Criteria

1. WHEN parsed text is available, THE Field_Extractor SHALL extract the title field from document headers or "작품명"/"제목" labels
2. WHEN parsed text is available, THE Field_Extractor SHALL extract the logline field from "로그라인"/"한줄 소개" labels
3. IF logline is not found, THEN THE Field_Extractor SHALL generate a 40-character summary from the synopsis first sentence and mark it as inferred
4. WHEN parsed text is available, THE Field_Extractor SHALL extract the synopsis field from "시놉시스"/"줄거리" sections
5. WHEN parsed text is available, THE Field_Extractor SHALL extract the characterDescription field from "등장인물"/"캐릭터" sections
6. WHEN parsed text is available, THE Field_Extractor SHALL extract the episodes field by matching patterns "총 N화"/"N부작"/"N회" and return as integer
7. WHEN parsed text is available, THE Field_Extractor SHALL extract the runtime field by matching patterns "회당 N분"/"편당 N분" and return as integer minutes
8. WHEN parsed text is available, THE Field_Extractor SHALL extract the genre field from "장르" labels and split multiple genres into an array
9. WHEN parsed text is available, THE Field_Extractor SHALL extract the productionYear field by matching 4-digit year patterns between 2020-2030
10. WHEN parsed text is available, THE Field_Extractor SHALL extract the productionStatus field by matching keywords "기획중"/"제작중"/"완성"/"완료"
11. IF productionStatus contains "완료" or "방영완료", THEN THE Field_Extractor SHALL normalize it to "완성"
12. FOR ALL fields that cannot be extracted, THE Field_Extractor SHALL return null

### Requirement 3: Confidence Level Assignment

**User Story:** As a Production_Company, I want to know the reliability of each extracted field, so that I can prioritize manual review of uncertain data.

#### Acceptance Criteria

1. WHEN a field is extracted using explicit label matching, THE Metadata_Validator SHALL assign "high" confidence
2. WHEN a field is extracted using pattern matching without explicit labels, THE Metadata_Validator SHALL assign "medium" confidence
3. WHEN a field is extracted through inference or uncertain matching, THE Metadata_Validator SHALL assign "low" confidence
4. WHEN a field is generated from other fields (like logline from synopsis), THE Metadata_Validator SHALL assign "inferred" confidence
5. THE Metadata_Validator SHALL include confidence levels for all 9 fields in the response

### Requirement 4: Structured JSON Output

**User Story:** As a Production_Company, I want to receive extracted metadata in a structured format, so that the Spring Boot backend can save it to RDS.

#### Acceptance Criteria

1. THE Pitch_Extractor SHALL return a JSON object containing extractedAt timestamp in ISO 8601 format
2. THE Pitch_Extractor SHALL return a JSON object containing parsingMethod field indicating which parser was used
3. THE Pitch_Extractor SHALL return a JSON object containing a fields object with all 9 metadata fields
4. THE Pitch_Extractor SHALL return a JSON object containing a confidence object with confidence levels for all 9 fields
5. THE Pitch_Extractor SHALL return a JSON object containing a missingFields array listing field names that are null
6. FOR ALL extracted Korean text, THE Pitch_Extractor SHALL preserve the original Korean characters without translation

### Requirement 5: Korean Language Support

**User Story:** As a Production_Company, I want the system to correctly handle Korean text in pitch PDFs, so that metadata is extracted accurately without language corruption.

#### Acceptance Criteria

1. THE PDF_Parser SHALL support UTF-8 encoding for Korean characters (가-힣 range)
2. THE Field_Extractor SHALL recognize Korean field labels ("작품명", "로그라인", "시놉시스", etc.)
3. THE Field_Extractor SHALL preserve Korean text formatting including line breaks and punctuation
4. THE Fallback_Detector SHALL calculate Korean character ratio using Unicode range U+AC00 to U+D7A3

### Requirement 6: Error Handling and Graceful Degradation

**User Story:** As a Production_Company, I want the system to handle extraction failures gracefully, so that I receive partial results instead of complete failure.

#### Acceptance Criteria

1. IF opendataloader-pdf raises an exception, THEN THE PDF_Parser SHALL trigger Upstage Document Parse API fallback
2. IF Upstage Document Parse API fails, THEN THE Pitch_Extractor SHALL return an error response with the failure reason
3. IF a specific field cannot be extracted, THEN THE Pitch_Extractor SHALL return null for that field and continue processing other fields
4. IF the PDF contains only images without extractable text, THEN THE Pitch_Extractor SHALL return null for all fields and indicate OCR limitation
5. THE Pitch_Extractor SHALL log all parsing attempts and fallback triggers to CloudWatch

### Requirement 7: Credit Conservation

**User Story:** As a Production_Company, I want the system to minimize Upstage API credit usage, so that operational costs remain low.

#### Acceptance Criteria

1. THE PDF_Parser SHALL use opendataloader-pdf for all initial parsing attempts
2. THE Fallback_Detector SHALL only trigger Upstage Document Parse API when quality thresholds are not met
3. THE Pitch_Extractor SHALL log Upstage API usage to CloudWatch for cost monitoring
4. THE Pitch_Extractor SHALL include parsingMethod in the response to track which parser was used

### Requirement 8: Integration with Spring Boot Backend

**User Story:** As a Production_Company, I want the extracted metadata to be saved to the database automatically, so that I can review and edit it in the registration form.

#### Acceptance Criteria

1. WHEN extraction completes, THE Pitch_Extractor SHALL return JSON to the Spring Boot backend
2. THE Spring Boot backend SHALL save the extracted fields to RDS in the drafts table
3. THE Spring Boot backend SHALL save the confidence levels to RDS for UI display
4. THE Spring Boot backend SHALL save the missingFields array to RDS to highlight incomplete data
5. THE Spring Boot backend SHALL provide a human review interface for low-confidence fields

### Requirement 9: Production Monitoring

**User Story:** As a Production_Company, I want the system to be monitored for performance and reliability, so that issues are detected before they impact the 5/14 showcase.

#### Acceptance Criteria

1. THE Pitch_Extractor SHALL log token usage to CloudWatch for each extraction request
2. THE Pitch_Extractor SHALL log extraction latency to CloudWatch for each request
3. THE Pitch_Extractor SHALL log error rates to CloudWatch including parsing failures and API errors
4. THE Pitch_Extractor SHALL log fallback trigger rates to CloudWatch to track Upstage API usage
5. THE Pitch_Extractor SHALL emit CloudWatch metrics for extraction success rate by parsing method

### Requirement 10: Skill System Integration

**User Story:** As a Production_Company, I want the pitch extraction feature to be available as a skill in the Deep Insight platform, so that it loads efficiently when needed.

#### Acceptance Criteria

1. THE Pitch_Extractor SHALL be implemented as a "pitch-extraction" skill following the Claude Code skill system pattern
2. THE Pitch_Extractor SHALL use lazy loading to minimize initial context size
3. THE Pitch_Extractor SHALL declare allowed tools (bash_tool, file_read, file_write) in the skill metadata
4. THE Pitch_Extractor SHALL include a description field with Korean trigger phrases ("기획안 읽어줘", "PDF에서 정보 뽑아줘")
5. THE Pitch_Extractor SHALL be discoverable through the skill discovery system
