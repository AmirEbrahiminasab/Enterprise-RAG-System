import asyncio
from io import BytesIO
from pathlib import Path

from fastapi import HTTPException, UploadFile
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from config.s3 import read_from_s3


def _extract_text_from_bytes(contents: bytes, filename: str) -> str:
    extension = Path(filename).suffix.lower()

    if extension == ".txt":
        try:
            return contents.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=400, detail="Text file must be UTF-8 encoded."
            )

    elif extension == ".pdf":
        reader = PdfReader(BytesIO(contents))

        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

        return text

    raise HTTPException(
        status_code=400, detail="Only .pdf and .txt files are supported."
    )


async def extract_text(file: UploadFile) -> str:
    contents = await file.read()
    return _extract_text_from_bytes(contents, file.filename)


def extract_and_chunk_text(file_path: str, filename: str) -> list:
    contents = asyncio.run(read_from_s3(file_path))
    text = _extract_text_from_bytes(contents, filename)

    separators = [
        "\n# ",
        "\n## ",
        "\n### ",
        "\n#### ",
        "\n```",
        "\n\n",
        "\n",
        ". ",
        "! ",
        "? ",
        "; ",
        ": ",
        ", ",
        " ",
        "",
    ]

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        separators=separators,
        keep_separator=True,
    )

    return splitter.split_text(text)
