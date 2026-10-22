import io

from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from research_council.studio.app import create_app


def pdf_bytes():
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    content = DecodedStreamObject()
    content.set_data(
        b"BT /F1 12 Tf 20 200 Td (Untrusted paper text: latency was not measured.) Tj ET"
    )
    page[NameObject("/Contents")] = writer._add_object(content)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def test_uploads_are_bounded_parsed_and_contained(tmp_path, monkeypatch):
    with TestClient(create_app(tmp_path)) as client:
        project = client.post(
            "/api/projects", json={"title": "PDF study", "topic": "Uploaded PDF study"}
        ).json()
        endpoint = "/api/projects/" + project["id"] + "/documents"
        response = client.post(
            endpoint, files=[("files", ("../../escape.pdf", pdf_bytes(), "application/pdf"))]
        )
        assert response.status_code == 200
        item = response.json()[0]
        assert item["status"] == "PARSED"
        assert item["filename"] == "escape.pdf"
        assert item["untrusted"] is True
        assert (tmp_path / item["path"]).is_relative_to(tmp_path)
        assert not (tmp_path.parent / "escape.pdf").exists()
        assert (
            client.post(
                endpoint,
                files={"files": ("script.pdf", b"<script>bad</script>", "application/pdf")},
            ).status_code
            == 422
        )
        assert (
            client.post(
                endpoint, files={"files": ("script.txt", b"%PDF-1.4", "text/plain")}
            ).status_code
            == 422
        )
        monkeypatch.setattr("research_council.studio.documents.MAX_DOCUMENT_BYTES", 10)
        assert (
            client.post(
                endpoint, files={"files": ("large.pdf", pdf_bytes(), "application/pdf")}
            ).status_code
            == 422
        )
        assert len(list((tmp_path / "documents").rglob("*.pdf"))) == 1
