from io import BytesIO
from pathlib import Path
from fastapi import HTTPException, UploadFile
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter


async def extract_text(file: UploadFile) -> str:
    extension = Path(file.filename).suffix.lower()
    contents = await file.read()

    if extension == ".txt":
        try:
            return contents.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=400,
                detail="Text file must be UTF-8 encoded."
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
        status_code=400,
        detail="Only .pdf and .txt files are supported."
    )

def extract_and_chunk_text(file: UploadFile) -> list:
    text = extract_text(file)

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
        ""
    ]

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        separators=separators,
        keep_separator=True,
    )

    return splitter.split_text(text)
