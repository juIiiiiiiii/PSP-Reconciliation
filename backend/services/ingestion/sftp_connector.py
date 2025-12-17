"""
SFTP Connector - Downloads settlement files from PSP SFTP servers
"""

import json
import logging
import os
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any
from uuid import UUID

import paramiko
import boto3

from services.ingestion.file_connector import FileConnector

logger = logging.getLogger(__name__)

s3_client = boto3.client('s3')
secrets_manager = boto3.client('secretsmanager')


class SFTPConnector:
    """Handles SFTP connections and file downloads"""
    
    def __init__(
        self,
        s3_bucket: str,
        kinesis_stream: str,
        parser_registry: Dict[str, Any]
    ):
        self.s3_bucket = s3_bucket
        self.kinesis_stream = kinesis_stream
        self.parser_registry = parser_registry
        self.file_connector = FileConnector(s3_bucket, kinesis_stream, parser_registry)
    
    async def download_settlement_file(
        self,
        tenant_id: UUID,
        psp_connection_id: str,
        target_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Download settlement file from PSP SFTP
        
        Args:
            tenant_id: Tenant ID
            psp_connection_id: PSP connection ID
            target_date: Date to download (defaults to yesterday)
        
        Returns:
            Download result with file path and processing status
        """
        if not target_date:
            target_date = date.today() - timedelta(days=1)
        
        try:
            # Get PSP connection config
            psp_config = await self._get_psp_config(tenant_id, psp_connection_id)
            
            if psp_config.get('connector_type') != 'SFTP':
                raise ValueError(f"PSP connection {psp_connection_id} is not SFTP type")
            
            # Get SFTP credentials from Secrets Manager
            sftp_config = await self._get_sftp_credentials(psp_config)
            
            # Connect to SFTP
            sftp_client = await self._connect_sftp(sftp_config)
            
            try:
                # Determine file path pattern (PSP-specific)
                remote_path = self._build_remote_path(
                    psp_config, target_date
                )
                
                # Download file
                local_path = await self._download_file(
                    sftp_client, remote_path, tenant_id, psp_connection_id, target_date
                )
                
                # Process file
                result = await self.file_connector.process_file(
                    tenant_id, psp_connection_id, local_path, 'SFTP'
                )
                
                return {
                    'status': 'success',
                    'remote_path': remote_path,
                    'local_path': local_path,
                    's3_path': result.get('s3_path'),
                    'events_count': result.get('events_count')
                }
                
            finally:
                sftp_client.close()
                
        except Exception as e:
            logger.error(f"Error downloading SFTP file: {str(e)}", exc_info=True)
            raise
    
    async def _get_psp_config(
        self,
        tenant_id: UUID,
        psp_connection_id: str
    ) -> Dict[str, Any]:
        """Get PSP connection configuration"""
        # TODO: Implement database lookup
        return {}
    
    async def _get_sftp_credentials(
        self,
        psp_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get SFTP credentials from Secrets Manager"""
        secret_arn = psp_config.get('authentication_secret_arn')
        if not secret_arn:
            raise ValueError("No SFTP credentials configured")
        
        secret = secrets_manager.get_secret_value(SecretId=secret_arn)
        return json.loads(secret['SecretString'])
    
    async def _connect_sftp(
        self,
        sftp_config: Dict[str, Any]
    ) -> paramiko.SFTPClient:
        """Connect to SFTP server"""
        transport = paramiko.Transport((
            sftp_config['host'],
            sftp_config.get('port', 22)
        ))
        
        transport.connect(
            username=sftp_config['username'],
            password=sftp_config.get('password'),
            pkey=paramiko.RSAKey.from_private_key_file(sftp_config['private_key_path'])
            if sftp_config.get('private_key_path') else None
        )
        
        return paramiko.SFTPClient.from_transport(transport)
    
    def _build_remote_path(
        self,
        psp_config: Dict[str, Any],
        target_date: date
    ) -> str:
        """Build remote file path based on PSP pattern"""
        # PSP-specific path patterns
        pattern = psp_config.get('sftp_path_pattern', '/settlements/{date}.csv')
        
        # Replace placeholders
        path = pattern.replace('{date}', target_date.strftime('%Y%m%d'))
        path = path.replace('{year}', str(target_date.year))
        path = path.replace('{month}', f"{target_date.month:02d}")
        path = path.replace('{day}', f"{target_date.day:02d}")
        
        return path
    
    async def _download_file(
        self,
        sftp_client: paramiko.SFTPClient,
        remote_path: str,
        tenant_id: UUID,
        psp_connection_id: str,
        target_date: date
    ) -> str:
        """Download file from SFTP to local temp, then upload to S3"""
        import tempfile
        
        # Create temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp_file:
            local_path = tmp_file.name
            
            # Download from SFTP
            sftp_client.get(remote_path, local_path)
            
            # Upload to S3
            s3_key = f"settlements/{tenant_id}/{target_date.strftime('%Y/%m/%d')}/{psp_connection_id}_{os.path.basename(remote_path)}"
            s3_client.upload_file(
                local_path,
                self.s3_bucket,
                s3_key
            )
            
            # Clean up temp file
            os.unlink(local_path)
            
            return f"s3://{self.s3_bucket}/{s3_key}"

