"""Private Dropbox storage for staff-uploaded CVs.

Only the backend talks to Dropbox. No shared links or OAuth credentials are
returned to the browser, and provider error bodies are never exposed.
"""

from __future__ import annotations

import json

import httpx

from app.core.config import settings

_API = "https://api.dropboxapi.com"
_CONTENT = "https://content.dropboxapi.com"


class DropboxStorageError(Exception):
    pass


def _root_path() -> str:
    parts = [part for part in settings.dropbox_root.replace("\\", "/").split("/") if part]
    if any(part in {".", ".."} for part in parts):
        raise DropboxStorageError("Некоректна папка Dropbox")
    return "/" + "/".join(parts) if parts else ""


def _credentials() -> tuple[str, str, str]:
    credentials = (
        settings.dropbox_app_key.get_secret_value(),
        settings.dropbox_app_secret.get_secret_value(),
        settings.dropbox_refresh_token.get_secret_value(),
    )
    if not all(credentials):
        raise DropboxStorageError("Підключення Dropbox не налаштоване на сервері")
    return credentials


async def _token(client: httpx.AsyncClient) -> str:
    key, secret, refresh = _credentials()
    try:
        response = await client.post(
            f"{_API}/oauth2/token",
            data={"grant_type": "refresh_token", "refresh_token": refresh,
                  "client_id": key, "client_secret": secret},
        )
        response.raise_for_status()
        token = response.json().get("access_token")
        if not isinstance(token, str) or not token:
            raise DropboxStorageError("Dropbox не повернув токен доступу")
        return token
    except (httpx.HTTPError, ValueError) as exc:
        raise DropboxStorageError("Не вдалося авторизуватися в Dropbox") from exc


async def _ensure_root(client: httpx.AsyncClient, token: str, root: str) -> None:
    if not root:
        return
    try:
        current = ""
        for part in root.strip("/").split("/"):
            current += "/" + part
            response = await client.post(
                f"{_API}/2/files/create_folder_v2",
                headers={"Authorization": f"Bearer {token}"},
                json={"path": current, "autorename": False},
            )
            # A 409 normally means this folder already exists. If an
            # intermediate path is a file, the following request fails.
            if response.status_code != 409:
                response.raise_for_status()
    except httpx.HTTPError as exc:
        raise DropboxStorageError("Не вдалося підготувати папку Dropbox") from exc


async def upload_cv(*, document_id: str, person_id: str, extension: str,
                    content: bytes, client: httpx.AsyncClient | None = None) -> str:
    """Upload a new private file and return its Dropbox file id."""
    if client is None:
        async with httpx.AsyncClient(timeout=45) as owned_client:
            return await upload_cv(document_id=document_id, person_id=person_id,
                                   extension=extension, content=content, client=owned_client)
    token = await _token(client)
    root = _root_path()
    await _ensure_root(client, token, root)
    path = f"{root}/{person_id}_{document_id}.{extension}"
    try:
        response = await client.post(
            f"{_CONTENT}/2/files/upload",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/octet-stream",
                "Dropbox-API-Arg": json.dumps(
                    {"path": path, "mode": "add", "autorename": False,
                     "mute": True, "strict_conflict": True},
                    ensure_ascii=True,
                ),
            },
            content=content,
        )
        response.raise_for_status()
        file_id = response.json().get("id")
        if not isinstance(file_id, str) or not file_id.startswith("id:"):
            raise DropboxStorageError("Dropbox не підтвердив збереження файлу")
        return file_id
    except (httpx.HTTPError, ValueError) as exc:
        raise DropboxStorageError("Не вдалося завантажити CV у Dropbox") from exc


async def download_cv(file_id: str, *, client: httpx.AsyncClient | None = None) -> bytes:
    if not file_id.startswith("id:"):
        raise DropboxStorageError("Некоректний ідентифікатор файлу Dropbox")
    if client is None:
        async with httpx.AsyncClient(timeout=45) as owned_client:
            return await download_cv(file_id, client=owned_client)
    token = await _token(client)
    try:
        response = await client.post(
            f"{_CONTENT}/2/files/download",
            headers={"Authorization": f"Bearer {token}",
                     "Dropbox-API-Arg": json.dumps({"path": file_id})},
        )
        response.raise_for_status()
        return response.content
    except httpx.HTTPError as exc:
        raise DropboxStorageError("Не вдалося отримати CV з Dropbox") from exc


async def delete_cv(file_id: str, *, client: httpx.AsyncClient | None = None) -> None:
    """Compensate a successful upload if recording its metadata fails."""
    if not file_id.startswith("id:"):
        raise DropboxStorageError("Некоректний ідентифікатор файлу Dropbox")
    if client is None:
        async with httpx.AsyncClient(timeout=30) as owned_client:
            return await delete_cv(file_id, client=owned_client)
    token = await _token(client)
    try:
        response = await client.post(
            f"{_API}/2/files/delete_v2",
            headers={"Authorization": f"Bearer {token}"},
            json={"path": file_id},
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise DropboxStorageError("Не вдалося прибрати незареєстрований CV із Dropbox") from exc
