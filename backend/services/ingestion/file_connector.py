"""
File Connector - Handles SFTP, Email, and Manual File Uploads
"""

import csv
import io
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from uuid import UUID, uuid4

import boto3
import openpyxl
from fastapi import UploadFile

from services.ingestion.parsers.base import BaseParser

logger = logging.getLogger(__name__)

s3_client = boto3.client('s3')
kinesis_client = boto3.client('kinesis')


class FileConnector:
    """Handles file-based ingestion (SFTP, Email, Manual)"""
    
    def __init__(
        self,
        s3_bucket: str,
        kinesis_stream: str,
        parser_registry: Dict[str, BaseParser]
    ):
        self.s3_bucket = s3_bucket
        self.kinesis_stream = kinesis_stream
        self.parser_registry = parser_registry
    
    async def process_file(
        self,
        tenant_id: UUID,
        psp_connection_id: str,
        file: UploadFile,
        file_type: str = "MANUAL"
    ) -> Dict[str, Any]:
        """
        Process uploaded file (CSV, XLSX, etc.)
        
        Steps:
        1. Upload file to S3
        2. Parse file based on parser version
        3. Publish parsed events to Kinesis
        """
        try:
            # Read file content
            content = await file.read()
            
            # Determine file format
            file_format = self._detect_file_format(file.filename, content)
            
            # Get parser for this PSP
            parser = self._get_parser(psp_connection_id, file_format)
            
            # Store file in S3
            s3_path = await self._store_file(
                tenant_id, psp_connection_id, file.filename, content
            )
            
            # Parse file
            events = await parser.parse(content, file_format)
            
            # Publish events to Kinesis
            published_count = 0
            for event in events:
                await self._publish_event(
                    tenant_id, psp_connection_id, event, s3_path, file_type
                )
                published_count += 1
            
            return {
                "status": "processed",
                "s3_path": s3_path,
                "events_count": published_count,
                "parser_version": parser.version
            }
            
        except Exception as e:
            logger.error(f"Error processing file: {str(e)}", exc_info=True)
            raise
    
    async def process_sftp_file(
        self,
        tenant_id: UUID,
        psp_connection_id: str,
        file_path: str
    ) -> Dict[str, Any]:
        """Process file from SFTP (scheduled job)"""
        # Download from SFTP (implementation depends on SFTP library)
        # Then process similar to manual upload
        pass
    
    async def process_email_attachment(
        self,
        tenant_id: UUID,
        psp_connection_id: str,
        email_message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process settlement file from email attachment"""
        # Extract attachment from email
        # Then process similar to manual upload
        pass
    
    def _detect_file_format(self, filename: str, content: bytes) -> str:
        """Detect file format from filename and content"""
        ext = Path(filename).suffix.lower()
        
        if ext == '.csv':
            return 'CSV'
        elif ext in ['.xlsx', '.xls']:
            return 'XLSX'
        elif ext == '.json':
            return 'JSON'
        elif ext == '.pdf':
            return 'PDF'  # Requires OCR/text extraction
        else:
            raise ValueError(f"Unsupported file format: {ext}")
    
    def _get_parser(
        self,
        psp_connection_id: str,
        file_format: str
    ) -> BaseParser:
        """Get parser for PSP and file format"""
        parser_key = f"{psp_connection_id}:{file_format}"
        
        if parser_key not in self.parser_registry:
            raise ValueError(f"No parser found for {parser_key}")
        
        return self.parser_registry[parser_key]
    
    async def _store_file(
        self,
        tenant_id: UUID,
        psp_connection_id: str,
        filename: str,
        content: bytes
    ) -> str:
        """Store file in S3"""
        date_str = datetime.utcnow().strftime('%Y/%m/%d')
        file_id = uuid4()
        s3_key = f"settlements/{tenant_id}/{date_str}/{file_id}_{filename}"
        
        s3_client.put_object(
            Bucket=self.s3_bucket,
            Key=s3_key,
            Body=content,
            ServerSideEncryption='AES256'
        )
        
        return f"s3://{self.s3_bucket}/{s3_key}"
    
    async def _publish_event(
        self,
        tenant_id: UUID,
        psp_connection_id: str,
        event: Dict[str, Any],
        s3_path: str,
        source_type: str
    ):
        """Publish parsed event to Kinesis"""
        record = {
            'tenant_id': str(tenant_id),
            'psp_connection_id': psp_connection_id,
            's3_path': s3_path,
            'event_data': event,
            'ingestion_timestamp': datetime.utcnow().isoformat(),
            'source_type': source_type
        }
        
        kinesis_client.put_record(
            StreamName=self.kinesis_stream,
            Data=json.dumps(record),
            PartitionKey=str(tenant_id)
        )

