import logging
from pathlib import Path
from typing import Any, Optional

import boto3
import urllib3
from boto3_type_annotations.s3 import Client

from overhave.transport.s3.models import BucketsListModel
from overhave.transport.s3.objects import OverhaveS3Bucket
from overhave.transport.s3.settings import S3ManagerSettings

logger = logging.getLogger(__name__)


class BaseS3ManagerException(Exception):
    """ Base exception for :class:`S3Manager`. """


class UndefinedClientException(BaseS3ManagerException):
    """ Exception for situation with not initialized client in :class:`S3Manager`. """


class S3Manager:
    """ Class for s3 management with boto3 client. """

    def __init__(self, settings: S3ManagerSettings):
        self._settings = settings
        self._client: Optional[Client] = None

    def initialize(self) -> None:
        if not self._settings.enabled:
            return
        self._client = self._get_client(self._settings)
        self._ensure_buckets_exists()

    @property
    def enabled(self) -> bool:
        return self._client is not None

    @staticmethod
    def _get_client(settings: S3ManagerSettings) -> Client:
        if not settings.verify:
            logger.warning("Verification disabled in '%s', so ignore 'urllib3' warnings.", type(settings).__name__)
            urllib3.disable_warnings()
        client = boto3.client(
            "s3",
            region_name=settings.region_name,
            verify=settings.verify,
            endpoint_url=settings.url,
            aws_access_key_id=settings.access_key,
            aws_secret_access_key=settings.secret_key,
        )
        logger.info("s3 client successfully initialized.")
        return client  # noqa: R504

    @property
    def _ensured_client(self) -> Client:
        if self._client is None:
            raise UndefinedClientException("s3 client has not been initialized!")
        return self._client

    def _ensure_buckets_exists(self) -> None:
        remote_buckets = self._get_buckets()
        logger.info("Existing remote s3 buckets: %s", remote_buckets.items)
        bucket_names = [model.name for model in remote_buckets.items]
        for bucket in list(filter(lambda x: x.value not in bucket_names, OverhaveS3Bucket)):
            self._create_bucket(bucket)
        logger.info("Successfully ensured existence of Overhave service buckets.")

    def _get_buckets(self) -> BucketsListModel:
        return BucketsListModel.parse_obj(self._ensured_client.list_buckets().get("Buckets"))

    def _create_bucket(self, bucket: OverhaveS3Bucket) -> None:
        logger.info("Creating bucket %s...", bucket)
        kwargs = {"Bucket": bucket.value}
        if isinstance(self._settings.region_name, str):
            kwargs["CreateBucketConfiguration"] = {"LocationConstraint": self._settings.region_name}
        self._ensured_client.create_bucket(**kwargs)
        logger.info("Bucket %s successfully created.", bucket)

    def upload_file(self, file: Path, bucket: OverhaveS3Bucket) -> Any:
        logger.info("Start uploading file '%s'...", file.name)
        result = self._ensured_client.upload_file(file.as_posix(), bucket.value, file.name)
        logger.info("Result: %s", result)
        logger.info("File '%s' successfully uploaded", file.name)
        return result
