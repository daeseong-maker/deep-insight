"""
Pitch Extraction Module

This module provides automated metadata extraction from Korean pitch PDFs
for the ShortFlow content registration system.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from datetime import datetime
import re
import os
import base64
import requests
import logging
import tempfile
import json
import opendataloader_pdf
from pypdf import PdfReader
import boto3
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Bedrock client
bedrock_runtime = boto3.client('bedrock-runtime', region_name=os.getenv('AWS_REGION', 'us-west-2'))


@dataclass
class ParseResult:
    """Result from PDF parsing operation."""
    success: bool
    text: str
    method: str  # "opendataloader" or "upstage_dp"
    error: Optional[str] = None
    page_count: int = 0


@dataclass
class FieldSet:
    """Container for extracted metadata fields."""
    title: Optional[str] = None
    logline: Optional[str] = None
    synopsis: Optional[str] = None
    character_description: Optional[str] = None
    episodes: Optional[int] = None
    runtime: Optional[int] = None
    genre: Optional[List[str]] = None
    production_year: Optional[int] = None
    production_status: Optional[str] = None


@dataclass
class ExtractionResult:
    """Complete extraction result with metadata."""
    extracted_at: str  # ISO 8601 timestamp
    parsing_method: str  # "opendataloader" or "upstage_dp"
    fields: FieldSet
    confidence: Dict[str, str]
    missing_fields: List[str]


class PDFParser:
    """Handles PDF parsing using two-stage strategy."""
    
    def __init__(self):
        """Initialize PDFParser with Upstage API configuration."""
        self.upstage_api_key = os.getenv('UPSTAGE_API_KEY')
        self.upstage_api_url = 'https://api.upstage.ai/v1/document-digitization'
    
    def parse(self, pdf_path: str) -> ParseResult:
        """
        Parse PDF using two-stage strategy.
        
        Args:
            pdf_path: Absolute path to PDF file
            
        Returns:
            ParseResult with text, method, and success status
        """
        # Stage 1: Try opendataloader-pdf first (free, local parsing)
        try:
            logger.info(f"Stage 1: Attempting opendataloader-pdf parsing for {pdf_path}")
            
            # Create temporary output directory
            with tempfile.TemporaryDirectory() as temp_dir:
                # Convert PDF to markdown format
                opendataloader_pdf.convert(
                    input_path=[pdf_path],
                    output_dir=temp_dir,
                    format="text"
                )
                
                # Read the output text file
                pdf_basename = os.path.basename(pdf_path)
                pdf_name = os.path.splitext(pdf_basename)[0]
                output_file = os.path.join(temp_dir, f"{pdf_name}.txt")
                
                with open(output_file, 'r', encoding='utf-8') as f:
                    text = f.read()
                
                # Get page count by parsing the PDF with pypdf as fallback
                # (opendataloader-pdf doesn't directly expose page count in text mode)
                try:
                    reader = PdfReader(pdf_path)
                    page_count = len(reader.pages)
                except:
                    # Estimate page count from text length if pypdf fails
                    page_count = max(1, len(text) // 2000)
                
                logger.info(f"opendataloader-pdf succeeded: {len(text)} chars, {page_count} pages")
                
                return ParseResult(
                    success=True,
                    text=text,
                    method="opendataloader",
                    page_count=page_count
                )
            
        except Exception as e:
            logger.error(f"opendataloader-pdf failed: {e}")
            logger.info("Triggering Stage 2: Upstage Document Parse API fallback")
            
            # Stage 2: Fallback to Upstage Document Parse API
            return self._parse_with_upstage(pdf_path)
    
    def _parse_with_upstage(self, pdf_path: str) -> ParseResult:
        """
        Parse PDF using Upstage Document Parse API.
        
        Args:
            pdf_path: Absolute path to PDF file
            
        Returns:
            ParseResult with text, method, and success status
        """
        try:
            # Check if API key is configured
            if not self.upstage_api_key:
                error_msg = "UPSTAGE_API_KEY not configured"
                logger.error(error_msg)
                return ParseResult(
                    success=False,
                    text="",
                    method="upstage_dp",
                    error=error_msg,
                    page_count=0
                )
            
            # Call Upstage Document Parse API with multipart/form-data
            headers = {
                'Authorization': f'Bearer {self.upstage_api_key}'
            }
            
            with open(pdf_path, 'rb') as f:
                files = {
                    'document': f
                }
                data = {
                    'ocr': 'force',
                    'model': 'document-parse'
                }
                
                logger.info(f"Calling Upstage Document Parse API for {pdf_path}")
                response = requests.post(
                    self.upstage_api_url,
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=60
                )
            
            if response.status_code != 200:
                error_msg = f"Upstage API error: {response.status_code} {response.text}"
                logger.error(error_msg)
                return ParseResult(
                    success=False,
                    text="",
                    method="upstage_dp",
                    error=error_msg,
                    page_count=0
                )
            
            # Parse response
            result = response.json()
            
            # Log response structure for debugging
            logger.info(f"Upstage API response keys: {result.keys() if isinstance(result, dict) else 'not a dict'}")
            logger.info(f"Elements count: {len(result.get('elements', [])) if isinstance(result, dict) else 0}")
            
            # Extract text from elements array
            # Upstage API returns elements with text in content.html field
            elements = result.get('elements', []) if isinstance(result, dict) else []
            text_parts = []
            
            for elem in elements:
                if not isinstance(elem, dict):
                    continue
                    
                category = elem.get('category', '')
                # Skip figure elements, only extract text from paragraph/heading elements
                if category in ['paragraph', 'heading1', 'heading2', 'heading3', 'heading4', 'heading5', 'heading6']:
                    content = elem.get('content', {})
                    if not isinstance(content, dict):
                        continue
                    
                    html_text = content.get('html', '')
                    if html_text:
                        # Strip HTML tags to get plain text
                        plain_text = re.sub(r'<[^>]+>', '', html_text)
                        text_parts.append(plain_text)
            
            text = '\n'.join(text_parts)
            
            # Get page count from API response
            page_count = 0
            if isinstance(result, dict):
                api_info = result.get('api', {})
                if isinstance(api_info, dict):
                    page_count = api_info.get('pages', 0)
                
                if not page_count:
                    # Fallback: estimate from elements
                    page_count = max(1, len(elements) // 10) if elements else 0
            
            logger.info(f"Upstage Document Parse API succeeded: {len(text)} chars, {page_count} pages")
            
            return ParseResult(
                success=True,
                text=text,
                method="upstage_dp",
                page_count=page_count
            )
            
        except FileNotFoundError:
            error_msg = f"PDF file not found: {pdf_path}"
            logger.error(error_msg)
            return ParseResult(
                success=False,
                text="",
                method="upstage_dp",
                error=error_msg,
                page_count=0
            )
        except Exception as e:
            error_msg = f"Upstage parsing failed: {str(e)}"
            logger.error(error_msg)
            return ParseResult(
                success=False,
                text="",
                method="upstage_dp",
                error=error_msg,
                page_count=0
            )


class FallbackDetector:
    """Evaluates extraction quality and determines if fallback is needed."""
    
    def should_fallback(self, text: str, page_count: int) -> bool:
        """
        Determine if Upstage fallback is needed.
        
        Args:
            text: Extracted text from opendataloader-pdf
            page_count: Number of pages in PDF
            
        Returns:
            True if fallback is needed, False otherwise
        """
        # Threshold 1: Minimum text length
        if len(text) < 100:
            return True
        
        # Threshold 2: Korean character ratio
        korean_chars = sum(1 for c in text if '\uAC00' <= c <= '\uD7A3')
        if len(text) > 0 and korean_chars / len(text) < 0.1:
            return True
        
        # Threshold 3: Characters per page
        if page_count > 0 and len(text) / page_count < 50:
            return True
        
        return False


class FieldExtractor:
    """Extracts metadata fields from parsed text using LLM."""
    
    def __init__(self):
        """Initialize FieldExtractor with Bedrock client."""
        self.bedrock = boto3.client('bedrock-runtime', region_name=os.getenv('AWS_REGION', 'us-west-2'))
        self.model_id = 'anthropic.claude-3-haiku-20240307-v1:0'
        self.extraction_metadata = {}
    
    def extract_fields(self, text: str) -> Dict[str, Any]:
        """
        Extract all 9 metadata fields from text using LLM.
        
        Args:
            text: Parsed text from PDF
            
        Returns:
            Dictionary with field names as keys and extracted values
        """
        self.extraction_metadata = {}
        
        prompt = f"""다음 한국어 기획안 텍스트에서 메타데이터를 추출해주세요.

<기획안>
{text}
</기획안>

다음 9개 필드를 추출하고 JSON 형식으로 반환하세요:

1. title (제목/작품명): 작품의 제목
2. logline (로그라인/한줄소개): 작품을 한 줄로 요약한 설명
3. synopsis (시놉시스/줄거리): 작품의 전체 줄거리 (시놉시스 섹션 전체)
4. characterDescription (등장인물/인물소개): 주요 등장인물 설명 (인물 소개 섹션 전체)
5. episodes (회차): 총 몇 화인지 (숫자만, 예: 57)
6. runtime (러닝타임): 회당 몇 분인지 (숫자만, 예: 3)
7. genre (장르): 장르 목록 (배열, 예: ["로맨스", "판타지"])
8. productionYear (제작년도): 제작 연도 (숫자만, 예: 2026)
9. productionStatus (제작상태): 기획중/제작중/완성 중 하나

규칙:
- 찾을 수 없는 필드는 null로 반환
- "완료"나 "방영완료"는 "완성"으로 변환
- 숫자 필드(episodes, runtime, productionYear)는 정수로 반환
- genre는 배열로 반환
- JSON만 반환하고 다른 설명은 하지 마세요

JSON:"""

        try:
            response = self.bedrock.invoke_model(
                modelId=self.model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 4096,
                    "messages": [{
                        "role": "user",
                        "content": prompt
                    }]
                })
            )
            
            result = json.loads(response['body'].read())
            content = result['content'][0]['text']
            
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                fields = json.loads(json_match.group(0))
                
                # Set all fields to high confidence (LLM extraction)
                for field in ['title', 'logline', 'synopsis', 'characterDescription', 
                             'episodes', 'runtime', 'genre', 'productionYear', 'productionStatus']:
                    if fields.get(field) is not None:
                        self.extraction_metadata[field] = 'label_match'
                
                return fields
            else:
                logger.error("No JSON found in LLM response")
                return self._empty_fields()
                
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return self._empty_fields()
    
    def _empty_fields(self) -> Dict[str, Any]:
        """Return empty fields dictionary."""
        return {
            'title': None,
            'logline': None,
            'synopsis': None,
            'characterDescription': None,
            'episodes': None,
            'runtime': None,
            'genre': None,
            'productionYear': None,
            'productionStatus': None
        }


class MetadataValidator:
    """Assigns confidence levels to extracted fields."""
    
    def validate(self, fields: Dict[str, Any], extraction_metadata: Dict) -> Dict[str, str]:
        """
        Assign confidence levels to extracted fields.
        
        Args:
            fields: Extracted field values
            extraction_metadata: Metadata about how each field was extracted
            
        Returns:
            Dictionary mapping field names to confidence levels
        """
        confidence = {}
        
        # All 9 fields that need confidence levels
        field_names = [
            'title', 'logline', 'synopsis', 'characterDescription',
            'episodes', 'runtime', 'genre', 'productionYear', 'productionStatus'
        ]
        
        for field_name in field_names:
            # Get extraction method from metadata
            extraction_method = extraction_metadata.get(field_name)
            
            # Assign confidence based on extraction method
            if extraction_method == 'label_match':
                confidence[field_name] = 'high'
            elif extraction_method == 'pattern_match':
                confidence[field_name] = 'medium'
            elif extraction_method == 'inferred':
                confidence[field_name] = 'inferred'
            else:
                # Field was not extracted or uncertain
                confidence[field_name] = 'low'
        
        return confidence


class PitchExtractor:
    """Orchestrates the extraction pipeline."""
    
    def __init__(self):
        self.pdf_parser = PDFParser()
        self.fallback_detector = FallbackDetector()
        self.field_extractor = FieldExtractor()
        self.metadata_validator = MetadataValidator()
    
    def extract(self, pdf_path: str) -> ExtractionResult:
        """
        Execute full extraction pipeline.
        
        Args:
            pdf_path: Absolute path to PDF file
            
        Returns:
            ExtractionResult with fields, confidence, and metadata
        """
        # Generate ISO 8601 timestamp
        extracted_at = datetime.utcnow().isoformat() + 'Z'
        
        try:
            # Step 1: Parse PDF using two-stage strategy
            logger.info(f"Starting extraction pipeline for {pdf_path}")
            parse_result = self.pdf_parser.parse(pdf_path)
            
            # Step 2: Check if parsing failed completely
            if not parse_result.success:
                logger.error(f"Parsing failed: {parse_result.error}")
                # Return error response when both parsers fail
                return self._create_error_result(
                    extracted_at=extracted_at,
                    error_message=f"PDF parsing failed: {parse_result.error}"
                )
            
            # Step 3: Detect if fallback is needed (only if using opendataloader)
            if parse_result.method == "opendataloader":
                should_fallback = self.fallback_detector.should_fallback(
                    parse_result.text, 
                    parse_result.page_count
                )
                
                if should_fallback:
                    logger.warning(
                        f"Fallback triggered for {pdf_path}",
                        extra={
                            "text_length": len(parse_result.text),
                            "page_count": parse_result.page_count
                        }
                    )
                    # Trigger Upstage fallback
                    parse_result = self.pdf_parser._parse_with_upstage(pdf_path)
                    
                    if not parse_result.success:
                        logger.error(f"Fallback parsing failed: {parse_result.error}")
                        return self._create_error_result(
                            extracted_at=extracted_at,
                            error_message=f"Fallback parsing failed: {parse_result.error}"
                        )
            
            # Step 4: Extract fields from parsed text
            logger.info(f"Extracting fields from {len(parse_result.text)} characters")
            fields_dict = self._extract_fields_with_error_handling(parse_result.text)
            
            # Step 5: Validate fields and assign confidence levels
            confidence = self.metadata_validator.validate(
                fields_dict,
                self.field_extractor.extraction_metadata
            )
            
            # Step 6: Identify missing fields
            missing_fields = [
                field_name for field_name, value in fields_dict.items()
                if value is None
            ]
            
            # Step 7: Create FieldSet from extracted fields
            field_set = FieldSet(
                title=fields_dict.get('title'),
                logline=fields_dict.get('logline'),
                synopsis=fields_dict.get('synopsis'),
                character_description=fields_dict.get('characterDescription'),
                episodes=fields_dict.get('episodes'),
                runtime=fields_dict.get('runtime'),
                genre=fields_dict.get('genre'),
                production_year=fields_dict.get('productionYear'),
                production_status=fields_dict.get('productionStatus')
            )
            
            # Step 8: Log extraction metrics to CloudWatch
            logger.info(
                "Extraction complete",
                extra={
                    "parsing_method": parse_result.method,
                    "extracted_fields": len([v for v in fields_dict.values() if v is not None]),
                    "missing_fields": missing_fields,
                    "pdf_path": pdf_path
                }
            )
            
            # Step 9: Return formatted output
            return ExtractionResult(
                extracted_at=extracted_at,
                parsing_method=parse_result.method,
                fields=field_set,
                confidence=confidence,
                missing_fields=missing_fields
            )
            
        except Exception as e:
            # Handle unexpected errors gracefully
            logger.error(
                f"Extraction pipeline failed with unexpected error: {str(e)}",
                extra={"pdf_path": pdf_path},
                exc_info=True
            )
            return self._create_error_result(
                extracted_at=extracted_at,
                error_message=f"Unexpected error: {str(e)}"
            )
    
    def _extract_fields_with_error_handling(self, text: str) -> Dict[str, Any]:
        """
        Extract fields with graceful error handling.
        
        Continue processing even if individual fields fail.
        
        Args:
            text: Parsed text from PDF
            
        Returns:
            Dictionary with field names and extracted values
        """
        fields = {}
        
        # Try to extract each field individually
        try:
            fields = self.field_extractor.extract_fields(text)
        except Exception as e:
            logger.error(f"Field extraction failed: {str(e)}", exc_info=True)
            # Return empty fields if extraction fails completely
            fields = {
                'title': None,
                'logline': None,
                'synopsis': None,
                'characterDescription': None,
                'episodes': None,
                'runtime': None,
                'genre': None,
                'productionYear': None,
                'productionStatus': None
            }
        
        return fields
    
    def _create_error_result(self, extracted_at: str, error_message: str) -> ExtractionResult:
        """
        Create an error result with all fields set to None.
        
        Args:
            extracted_at: ISO 8601 timestamp
            error_message: Error message to log
            
        Returns:
            ExtractionResult with empty fields
        """
        # Create empty field set
        field_set = FieldSet()
        
        # All fields have low confidence since extraction failed
        confidence = {
            'title': 'low',
            'logline': 'low',
            'synopsis': 'low',
            'characterDescription': 'low',
            'episodes': 'low',
            'runtime': 'low',
            'genre': 'low',
            'productionYear': 'low',
            'productionStatus': 'low'
        }
        
        # All fields are missing
        missing_fields = [
            'title', 'logline', 'synopsis', 'characterDescription',
            'episodes', 'runtime', 'genre', 'productionYear', 'productionStatus'
        ]
        
        return ExtractionResult(
            extracted_at=extracted_at,
            parsing_method="error",
            fields=field_set,
            confidence=confidence,
            missing_fields=missing_fields
        )
