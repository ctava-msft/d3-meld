import argparse
import concurrent.futures
import os
import sys
import time
import mimetypes
import base64
import json
import logging
from dataclasses import dataclass
from typing import List, Optional, Iterable, Tuple

from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
from azure.identity import ManagedIdentityCredential
from azure.storage.blob import BlobServiceClient, ContentSettings
from azure.core.exceptions import ResourceExistsError, ServiceRequestError, ServiceResponseError, ClientAuthenticationError
from azure.core.exceptions import ResourceNotFoundError, HttpResponseError

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class UploadResult:
    path: str
    blob_name: str
    size: int
    success: bool
    error: Optional[str] = None
    elapsed: float = 0.0


TRANSIENT_ERRORS = (ServiceRequestError, ServiceResponseError)


def iter_files(paths: List[str]) -> Iterable[Tuple[str, str]]:
    for base in paths:
        if os.path.isfile(base):
            yield os.path.dirname(base), base
        else:
            for root, _dirs, files in os.walk(base):
                for f in files:
                    full = os.path.join(root, f)
                    yield base, full


def guess_content_type(path: str) -> Optional[str]:
    ctype, _ = mimetypes.guess_type(path)
    return ctype


def upload_one(blob_service: BlobServiceClient,
               container: str,
               base_dir: str,
               file_path: str,
               dest_prefix: str,
               overwrite: bool,
               detect_content_type: bool,
               if_none_match: Optional[str],
               max_retries: int = 3,
               concurrency: int = 4) -> UploadResult:
    rel_path = os.path.relpath(file_path, start=base_dir)
    blob_name = f"{dest_prefix}/{rel_path}" if dest_prefix else rel_path
    blob_name = blob_name.replace("\\", "/")
    size = os.path.getsize(file_path)
    
    logger.debug(f"Preparing upload: {file_path} -> {blob_name} ({size} bytes)")
    
    start = time.time()
    client = blob_service.get_blob_client(container=container, blob=blob_name)

    attempt = 0
    while True:
        attempt += 1
        logger.debug(f"Upload attempt {attempt}/{max_retries + 1} for {blob_name}")
        try:
            with open(file_path, "rb") as data:
                kwargs = {}
                if not overwrite:
                    kwargs["overwrite"] = False
                else:
                    kwargs["overwrite"] = True
                if if_none_match:
                    kwargs["if_none_match"] = if_none_match
                    logger.debug(f"Using if_none_match condition: {if_none_match}")
                if detect_content_type:
                    ctype = guess_content_type(file_path)
                    if ctype:
                        kwargs["content_settings"] = ContentSettings(content_type=ctype)
                        logger.debug(f"Detected content type: {ctype}")
                
                logger.debug(f"Starting blob upload with max_concurrency={concurrency}")
                client.upload_blob(data, **kwargs, max_concurrency=concurrency)
            
            elapsed = time.time() - start
            logger.debug(f"Successfully uploaded {blob_name} in {elapsed:.2f}s")
            return UploadResult(path=file_path, blob_name=blob_name, size=size, success=True, elapsed=elapsed)
        except ResourceExistsError as rex:
            logger.debug(f"Blob already exists: {blob_name}")
            return UploadResult(path=file_path, blob_name=blob_name, size=size, success=False, error=str(rex), elapsed=time.time() - start)
        except ClientAuthenticationError as auth_err:
            logger.error(f"Authentication error for {blob_name}: {auth_err}")
            return UploadResult(path=file_path, blob_name=blob_name, size=size, success=False, error=f"Auth failure: {auth_err}", elapsed=time.time() - start)
        except TRANSIENT_ERRORS as tex:
            if attempt <= max_retries:
                backoff = min(2 ** attempt, 10)
                logger.warning(f"Transient error on attempt {attempt} for {blob_name}, retrying in {backoff}s: {tex}")
                time.sleep(backoff)
                continue
            logger.error(f"Transient error after {max_retries} retries for {blob_name}: {tex}")
            return UploadResult(path=file_path, blob_name=blob_name, size=size, success=False, error=f"Transient error after retries: {tex}", elapsed=time.time() - start)
        except Exception as ex:  # pylint: disable=broad-except
            logger.error(f"Unexpected error uploading {blob_name}: {ex}", exc_info=True)
            return UploadResult(path=file_path, blob_name=blob_name, size=size, success=False, error=str(ex), elapsed=time.time() - start)


def load_env_file():
    logger.debug("Loading .env file")
    load_dotenv(override=False)
    logger.debug(f"Environment variables loaded (AZURE_TENANT_ID={'set' if os.environ.get('AZURE_TENANT_ID') else 'not set'})")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Upload files/directories to an Azure Blob container using Entra ID auth.")
    group_src = p.add_mutually_exclusive_group(required=True)
    group_src.add_argument("--path", nargs="+", help="One or more file or directory paths to upload.")
    p.add_argument("--account-url", help="Full https URL for the storage account (e.g. https://<account>.blob.core.windows.net).")
    p.add_argument("--account-name", help="Storage account name (alternative to --account-url).")
    p.add_argument("--container", required=True, help="Target container name.")
    p.add_argument("--destination-prefix", default="", help="Prefix inside container under which to place files.")
    p.add_argument("--concurrency", type=int, default=8, help="Number of parallel file uploads.")
    p.add_argument("--per-file-concurrency", type=int, default=4, help="Max parallelism per single large blob upload.")
    p.add_argument("--detect-content-type", action="store_true", help="Infer content type via filename.")
    p.add_argument("--overwrite", action="store_true", help="Overwrite existing blobs.")
    p.add_argument("--if-none-match", help="ETag condition for upload (e.g. '*').")
    p.add_argument("--dry-run", action="store_true", help="List what would be uploaded without performing uploads.")
    p.add_argument("--verbose", action="store_true", help="Verbose logging.")
    p.add_argument("--tenant-id", help="Tenant ID (overrides AZURE_TENANT_ID env/.env if provided).")
    p.add_argument("--managed-identity", action="store_true", help="Use Managed Identity instead of DefaultAzureCredential chain (disables interactive login).")
    p.add_argument("--mi-client-id", help="Client ID of user-assigned managed identity (optional).")
    p.add_argument("--timeout", type=int, default=0, help="Overall timeout in seconds (0 = no timeout).")
    p.add_argument("--create-container", action="store_true", help="Create container if it does not exist.")
    p.add_argument("--show-claims", action="store_true", help="Print decoded AAD access token claims for debugging.")
    p.add_argument("--debug", action="store_true", help="Enable debug logging.")
    return p.parse_args()


def build_account_url(args: argparse.Namespace) -> str:
    if args.account_url:
        return args.account_url.rstrip('/')
    if args.account_name:
        return f"https://{args.account_name}.blob.core.windows.net"
    raise SystemExit("Must provide either --account-url or --account-name")


def _decode_jwt_segment(segment: str) -> dict:
    try:
        padding = '=' * (-len(segment) % 4)
        return json.loads(base64.urlsafe_b64decode(segment + padding).decode("utf-8"))
    except Exception:
        return {}


def main():
    args = parse_args()
    
    # Configure logging based on debug/verbose flags
    log_level = logging.DEBUG if args.debug else (logging.INFO if args.verbose else logging.WARNING)
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    logger.info("Starting blob upload script")
    logger.debug(f"Arguments: {vars(args)}")
    
    account_url = build_account_url(args)
    logger.debug(f"Using storage account URL: {account_url}")

    load_env_file()

    credential = None
    tenant_id = None

    if args.managed_identity:
        logger.info("Using Managed Identity authentication")
        if args.tenant_id:
            tenant_id = args.tenant_id
        else:
            tenant_id = os.environ.get("AZURE_TENANT_ID")
        
        logger.debug(f"Tenant ID: {tenant_id or '(not specified)'}")
        
        try:
            if args.mi_client_id:
                logger.debug(f"Using user-assigned managed identity: {args.mi_client_id}")
                credential = ManagedIdentityCredential(client_id=args.mi_client_id)
            else:
                logger.debug("Using system-assigned managed identity")
                credential = ManagedIdentityCredential()
        except Exception as ex:  # pylint: disable=broad-except
            logger.error(f"Failed to initialize ManagedIdentityCredential: {ex}", exc_info=True)
            print(f"ERROR: Failed to initialize ManagedIdentityCredential: {ex}", file=sys.stderr)
            sys.exit(3)
    else:
        logger.info("Using DefaultAzureCredential authentication chain")
        tenant_id = args.tenant_id or os.environ.get("AZURE_TENANT_ID")
        if not tenant_id:
            logger.error("Tenant ID not provided")
            print("ERROR: Tenant ID not provided. Use --tenant-id or set AZURE_TENANT_ID in environment/.env (or use --managed-identity).", file=sys.stderr)
            sys.exit(3)
        
        logger.debug(f"Setting AZURE_TENANT_ID environment variable: {tenant_id}")
        if "AZURE_TENANT_ID" not in os.environ:
            os.environ["AZURE_TENANT_ID"] = tenant_id
        credential = DefaultAzureCredential()

    # Validate tenant only if we have a desired tenant_id
    token_claims = {}
    if tenant_id:
        logger.debug("Acquiring token for storage.azure.com scope")
        try:
            token = credential.get_token("https://storage.azure.com/.default").token
            logger.debug("Token acquired successfully")
            parts = token.split('.')
            if len(parts) < 2:
                raise ValueError("Unexpected token format")
            token_claims = _decode_jwt_segment(parts[1])
            tid = token_claims.get('tid') or token_claims.get('tenantId')
            logger.debug(f"Token tenant ID: {tid}")
            if tid != tenant_id:
                logger.error(f"Token tenant mismatch: expected {tenant_id}, got {tid}")
                print(f"ERROR: Acquired token tenant {tid} does not match requested tenant {tenant_id}", file=sys.stderr)
                sys.exit(3)
            logger.info(f"Token validated for tenant: {tenant_id}")
        except Exception as ex:  # pylint: disable=broad-except
            logger.error(f"Failed to validate tenant id: {ex}", exc_info=True)
            print(f"ERROR: Failed to validate tenant id: {ex}", file=sys.stderr)
            sys.exit(3)

    if args.show_claims and token_claims:
        print("Token claims (subset):")
        for k in ("tid", "oid", "sub", "appid", "upn", "aud"):
            if k in token_claims:
                print(f"  {k}: {token_claims[k]}")

    logger.debug(f"Creating BlobServiceClient for {account_url}")
    blob_service = BlobServiceClient(account_url=account_url, credential=credential)
    
    logger.debug(f"Checking if container '{args.container}' exists")
    try:
        container_client = blob_service.get_container_client(args.container)
        props = container_client.get_container_properties()
        logger.info(f"Container '{args.container}' exists")
        logger.debug(f"Container properties: last_modified={props.last_modified}")
    except ResourceNotFoundError:
        logger.warning(f"Container '{args.container}' not found")
        if args.create_container:
            try:
                print(f"Container '{args.container}' not found. Creating...")
                logger.info(f"Creating container '{args.container}'")
                blob_service.create_container(args.container)
                print("Container created.")
                logger.info("Container created successfully")
            except Exception as ex:  # pylint: disable=broad-except
                logger.error(f"Failed to create container: {ex}", exc_info=True)
                print(f"ERROR: Failed to create container '{args.container}': {ex}", file=sys.stderr)
                sys.exit(2)
        else:
            print(f"ERROR: Container '{args.container}' not found. Use --create-container to create it.", file=sys.stderr)
            sys.exit(2)
    except ClientAuthenticationError as auth_err:
        logger.error(f"Authentication error accessing container: {auth_err}", exc_info=True)
        print(f"ERROR: Authentication / authorization failure accessing container '{args.container}': {auth_err}", file=sys.stderr)
        if args.show_claims and token_claims:
            print("Claims shown above may help diagnose role assignment (e.g. need 'Storage Blob Data Contributor').")
        sys.exit(2)
    except HttpResponseError as hre:
        code = getattr(hre, "error_code", None)
        logger.error(f"HTTP error accessing container (code={code}): {hre}", exc_info=True)
        if code == "AuthorizationFailure":
            print(f"ERROR: AuthorizationFailure accessing '{args.container}'. Principal may lack role 'Storage Blob Data Contributor' or 'Storage Blob Data Owner'.", file=sys.stderr)
            if args.show_claims and token_claims:
                oid = token_claims.get("oid")
                appid = token_claims.get("appid")
                print(f"Principal object id: {oid or '(n/a)'}  AppId (if app): {appid or '(n/a)'}")
            sys.exit(2)
        print(f"ERROR: Unable to access container '{args.container}': {hre}", file=sys.stderr)
        sys.exit(2)
    except Exception as ex:  # pylint: disable=broad-except
        logger.error(f"Unexpected error accessing container: {ex}", exc_info=True)
        print(f"ERROR: Unable to access container '{args.container}': {ex}", file=sys.stderr)
        sys.exit(2)

    logger.info("Discovering files to upload")
    files: List[Tuple[str, str]] = []
    for p in args.path:
        logger.debug(f"Processing path: {p}")
        if not os.path.exists(p):
            print(f"WARN: Path does not exist, skipping: {p}")
            logger.warning(f"Path does not exist: {p}")
            continue
        if os.path.isfile(p):
            files.append((os.path.dirname(p), p))
            logger.debug(f"Added file: {p}")
        else:
            for root, _dirs, fs in os.walk(p):
                for f in fs:
                    full_path = os.path.join(root, f)
                    files.append((p, full_path))
                    logger.debug(f"Added file from directory: {full_path}")

    if not files:
        print("No files found to upload.")
        logger.warning("No files found to upload")
        return

    total_bytes = sum(os.path.getsize(f[1]) for f in files)
    print(f"Discovered {len(files)} files totalling {total_bytes/1024/1024:.2f} MiB")
    logger.info(f"Discovered {len(files)} files totalling {total_bytes/1024/1024:.2f} MiB")
    
    if args.dry_run:
        logger.info("Dry-run mode: listing files only")
        for base, path in files:
            rel = os.path.relpath(path, start=base).replace('\\', '/')
            blob_name = f"{args.destination_prefix}/{rel}" if args.destination_prefix else rel
            print(f"DRY-RUN would upload {path} -> {args.container}:{blob_name}")
        return

    logger.info(f"Starting upload with {args.concurrency} parallel workers")
    start_all = time.time()
    results: List[UploadResult] = []

    def worker(item):
        base_dir, file_path = item
        return upload_one(blob_service,
                          args.container,
                          base_dir,
                          file_path,
                          args.destination_prefix,
                          args.overwrite,
                          args.detect_content_type,
                          args.if_none_match,
                          max_retries=3,
                          concurrency=args.per_file_concurrency)

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        future_to_item = {executor.submit(worker, it): it for it in files}
        completed = 0
        for future in concurrent.futures.as_completed(future_to_item):
            res: UploadResult = future.result()
            results.append(res)
            completed += 1
            
            if res.success:
                logger.info(f"[{completed}/{len(files)}] Uploaded {res.blob_name} ({res.size} bytes in {res.elapsed:.2f}s)")
                if args.verbose:
                    print(f"OK {res.blob_name} ({res.size} bytes in {res.elapsed:.2f}s)")
            else:
                logger.error(f"[{completed}/{len(files)}] Failed {res.blob_name}: {res.error}")
                print(f"FAIL {res.blob_name}: {res.error}", file=sys.stderr)

    elapsed_all = time.time() - start_all
    ok = sum(1 for r in results if r.success)
    fail = len(results) - ok
    uploaded_bytes = sum(r.size for r in results if r.success)
    throughput = uploaded_bytes/1024/1024/elapsed_all if elapsed_all > 0 else 0
    
    print(f"Completed in {elapsed_all:.2f}s. Success: {ok}  Failed: {fail}  Throughput: {throughput:.2f} MiB/s")
    logger.info(f"Upload completed - Success: {ok}, Failed: {fail}, Throughput: {throughput:.2f} MiB/s")
    
    if fail:
        logger.error(f"{fail} file(s) failed to upload")
        sys.exit(1)


if __name__ == "__main__":
    main()
