import argparse
import concurrent.futures
import os
import sys
import time
import mimetypes
import base64
import json
from dataclasses import dataclass
from typing import List, Optional, Iterable, Tuple

from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
from azure.identity import ManagedIdentityCredential
from azure.storage.blob import BlobServiceClient, ContentSettings
from azure.core.exceptions import ResourceExistsError, ServiceRequestError, ServiceResponseError, ClientAuthenticationError


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
    start = time.time()
    client = blob_service.get_blob_client(container=container, blob=blob_name)

    attempt = 0
    while True:
        attempt += 1
        try:
            with open(file_path, "rb") as data:
                kwargs = {}
                if not overwrite:
                    kwargs["overwrite"] = False
                else:
                    kwargs["overwrite"] = True
                if if_none_match:
                    # Set conditional header; azure-storage SDK expects 'if_none_match' arg in upload_blob
                    kwargs["if_none_match"] = if_none_match
                if detect_content_type:
                    ctype = guess_content_type(file_path)
                    if ctype:
                        kwargs["content_settings"] = ContentSettings(content_type=ctype)
                client.upload_blob(data, **kwargs, max_concurrency=concurrency)
            elapsed = time.time() - start
            return UploadResult(path=file_path, blob_name=blob_name, size=size, success=True, elapsed=elapsed)
        except ResourceExistsError as rex:
            # Occurs if overwrite False and blob exists
            return UploadResult(path=file_path, blob_name=blob_name, size=size, success=False, error=str(rex), elapsed=time.time() - start)
        except ClientAuthenticationError as auth_err:
            return UploadResult(path=file_path, blob_name=blob_name, size=size, success=False, error=f"Auth failure: {auth_err}", elapsed=time.time() - start)
        except TRANSIENT_ERRORS as tex:
            if attempt <= max_retries:
                time.sleep(min(2 ** attempt, 10))
                continue
            return UploadResult(path=file_path, blob_name=blob_name, size=size, success=False, error=f"Transient error after retries: {tex}", elapsed=time.time() - start)
        except Exception as ex:  # pylint: disable=broad-except
            return UploadResult(path=file_path, blob_name=blob_name, size=size, success=False, error=str(ex), elapsed=time.time() - start)


def load_env_file():
    # Use python-dotenv to load .env (does not override existing env vars by default)
    load_dotenv(override=False)


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
    return p.parse_args()


def build_account_url(args: argparse.Namespace) -> str:
    if args.account_url:
        return args.account_url.rstrip('/')
    if args.account_name:
        return f"https://{args.account_name}.blob.core.windows.net"
    raise SystemExit("Must provide either --account-url or --account-name")


def main():
    args = parse_args()
    account_url = build_account_url(args)

    # Load .env variables (non-destructive: existing os.environ wins)
    load_env_file()

    credential = None
    tenant_id = None

    if args.managed_identity:
        # Managed Identity scenario: tenant may not be required; specify client ID if user-assigned.
        if args.tenant_id:
            tenant_id = args.tenant_id
        else:
            tenant_id = os.environ.get("AZURE_TENANT_ID")  # optional
        try:
            if args.mi_client_id:
                credential = ManagedIdentityCredential(client_id=args.mi_client_id)
            else:
                credential = ManagedIdentityCredential()
        except Exception as ex:  # pylint: disable=broad-except
            print(f"ERROR: Failed to initialize ManagedIdentityCredential: {ex}", file=sys.stderr)
            sys.exit(3)
    else:
        # Default credential chain (interactive / CLI / VS Code / MI fallback)
        tenant_id = args.tenant_id or os.environ.get("AZURE_TENANT_ID")
        if not tenant_id:
            print("ERROR: Tenant ID not provided. Use --tenant-id or set AZURE_TENANT_ID in environment/.env (or use --managed-identity).", file=sys.stderr)
            sys.exit(3)
        # DefaultAzureCredential in current azure-identity version does NOT accept tenant_id kwarg.
        # Ensure environment variable is set so the chain honors the intended tenant.
        if "AZURE_TENANT_ID" not in os.environ:
            os.environ["AZURE_TENANT_ID"] = tenant_id
        credential = DefaultAzureCredential()

    # Validate tenant only if we have a desired tenant_id
    if tenant_id:
        try:
            token = credential.get_token("https://storage.azure.com/.default").token
            parts = token.split('.')
            if len(parts) < 2:
                raise ValueError("Unexpected token format")
            payload_segment = parts[1]
            padding = '=' * (-len(payload_segment) % 4)
            payload_json = base64.urlsafe_b64decode(payload_segment + padding).decode('utf-8')
            payload = json.loads(payload_json)
            tid = payload.get('tid') or payload.get('tenantId')
            if tid != tenant_id:
                print(f"ERROR: Acquired token tenant {tid} does not match requested tenant {tenant_id}", file=sys.stderr)
                sys.exit(3)
        except Exception as ex:  # pylint: disable=broad-except
            print(f"ERROR: Failed to validate tenant id: {ex}", file=sys.stderr)
            sys.exit(3)

    blob_service = BlobServiceClient(account_url=account_url, credential=credential)
    try:
        container_client = blob_service.get_container_client(args.container)
        # Verify access early
        container_client.get_container_properties()
    except ClientAuthenticationError as auth_err:
        print(f"ERROR: Authentication / authorization failure accessing container '{args.container}': {auth_err}", file=sys.stderr)
        sys.exit(2)
    except Exception as ex:  # pylint: disable=broad-except
        print(f"ERROR: Unable to access container '{args.container}': {ex}", file=sys.stderr)
        sys.exit(2)

    files: List[Tuple[str, str]] = []
    for p in args.path:
        if not os.path.exists(p):
            print(f"WARN: Path does not exist, skipping: {p}")
            continue
        if os.path.isfile(p):
            files.append((os.path.dirname(p), p))
        else:
            for root, _dirs, fs in os.walk(p):
                for f in fs:
                    files.append((p, os.path.join(root, f)))

    if not files:
        print("No files found to upload.")
        return

    total_bytes = sum(os.path.getsize(f[1]) for f in files)
    print(f"Discovered {len(files)} files totalling {total_bytes/1024/1024:.2f} MiB")
    if args.dry_run:
        for base, path in files:
            rel = os.path.relpath(path, start=base).replace('\\', '/')
            blob_name = f"{args.destination_prefix}/{rel}" if args.destination_prefix else rel
            print(f"DRY-RUN would upload {path} -> {args.container}:{blob_name}")
        return

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
        for future in concurrent.futures.as_completed(future_to_item):
            res: UploadResult = future.result()
            results.append(res)
            if res.success:
                if args.verbose:
                    print(f"OK {res.blob_name} ({res.size} bytes in {res.elapsed:.2f}s)")
            else:
                print(f"FAIL {res.blob_name}: {res.error}", file=sys.stderr)

    elapsed_all = time.time() - start_all
    ok = sum(1 for r in results if r.success)
    fail = len(results) - ok
    uploaded_bytes = sum(r.size for r in results if r.success)
    print(f"Completed in {elapsed_all:.2f}s. Success: {ok}  Failed: {fail}  Throughput: {uploaded_bytes/1024/1024/elapsed_all if elapsed_all>0 else 0:.2f} MiB/s")
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
