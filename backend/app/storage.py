import os
import tempfile
from abc import ABC, abstractmethod
from app.data_config import get_config, DATA_DIR


class StorageBackend(ABC):
    @abstractmethod
    def save(self, data: bytes, path: str, content_type: str = 'application/octet-stream') -> str: ...

    @abstractmethod
    def delete(self, path: str) -> None: ...

    @abstractmethod
    def test(self) -> None: ...  # raises on failure


class LocalStorage(StorageBackend):
    def __init__(self):
        self.base = os.path.join(DATA_DIR, 'documents')

    def save(self, data: bytes, path: str, content_type: str = 'application/octet-stream') -> str:
        full = os.path.join(self.base, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, 'wb') as f:
            f.write(data)
        return path

    def delete(self, path: str) -> None:
        full = os.path.join(self.base, path)
        if os.path.exists(full):
            os.remove(full)

    def test(self) -> None:
        os.makedirs(self.base, exist_ok=True)
        probe = os.path.join(self.base, '.probe')
        with open(probe, 'w') as f:
            f.write('ok')
        os.remove(probe)


class S3Storage(StorageBackend):
    def __init__(self, cfg: dict):
        import boto3
        from botocore.config import Config
        self.bucket = cfg['bucket']
        kwargs: dict = {
            'aws_access_key_id': cfg.get('access_key'),
            'aws_secret_access_key': cfg.get('secret_key'),
            'region_name': cfg.get('region') or 'us-east-1',
            'config': Config(signature_version='s3v4', s3={'addressing_style': 'path'}),
        }
        if cfg.get('endpoint'):
            kwargs['endpoint_url'] = cfg['endpoint']
        self.s3 = boto3.client('s3', **kwargs)

    def save(self, data: bytes, path: str, content_type: str = 'application/octet-stream') -> str:
        self.s3.put_object(Bucket=self.bucket, Key=path, Body=data, ContentType=content_type)
        return path

    def delete(self, path: str) -> None:
        self.s3.delete_object(Bucket=self.bucket, Key=path)

    def test(self) -> None:
        self.s3.head_bucket(Bucket=self.bucket)


class WebDAVStorage(StorageBackend):
    def __init__(self, cfg: dict):
        from webdav3.client import Client
        self.base = (cfg.get('path') or '/tracktion').rstrip('/')
        self.client = Client({
            'webdav_hostname': cfg['url'].rstrip('/'),
            'webdav_login': cfg.get('username', ''),
            'webdav_password': cfg.get('password', ''),
        })

    def _ensure_dirs(self, remote_dir: str) -> None:
        parts = remote_dir.strip('/').split('/')
        for i in range(len(parts)):
            path = '/' + '/'.join(parts[:i + 1])
            if not self.client.check(path):
                self.client.mkdir(path)

    def save(self, data: bytes, path: str, content_type: str = 'application/octet-stream') -> str:
        remote = f"{self.base}/{path}"
        parent = remote.rsplit('/', 1)[0]
        self._ensure_dirs(parent)
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        try:
            self.client.upload_sync(remote_path=remote, local_path=tmp_path)
        finally:
            os.unlink(tmp_path)
        return path

    def delete(self, path: str) -> None:
        remote = f"{self.base}/{path}"
        try:
            self.client.clean(remote)
        except Exception:
            pass

    def test(self) -> None:
        self.client.check(self.base or '/')


def get_storage() -> StorageBackend:
    cfg = get_config().get('storage', {})
    t = cfg.get('type', 'local')
    if t == 's3':
        return S3Storage(cfg)
    if t == 'webdav':
        return WebDAVStorage(cfg)
    return LocalStorage()
