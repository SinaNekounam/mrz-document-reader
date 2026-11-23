import tempfile
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException

from phase_4_mrz_models import MRZResult, TesseractProvider

app = FastAPI(
    title="MRZ Document Reader",
    description="Reads and verifies the machine-readable zone of a passport.",
    version="1.0.0",
)

provider = TesseractProvider()


@app.get("/health")
def health():
    """Simple check that the service is running."""
    return {"status": "ok"}


@app.post("/api/v1/mrz/read", response_model=MRZResult)
async def read_mrz_endpoint(file: UploadFile = File(...)):
    """
    Read and verify the MRZ from an uploaded passport image.

    The image is written to a temporary file because the OCR pipeline
    works on file paths. The temporary file is removed afterwards.
    """

    contents = await file.read()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        tmp.write(contents)
        temp_path = tmp.name

    try:
        result = provider.extract(temp_path)
    except Exception as error:
        raise HTTPException(status_code=422, detail=str(error))
    finally:
        Path(temp_path).unlink(missing_ok=True)

    return result
