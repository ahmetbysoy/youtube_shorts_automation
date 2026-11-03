"""Faz 4 birim testleri (src/youtube_upload/youtube_uploader.py)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import src.youtube_upload.youtube_uploader as yu


class TestFaz4YouTubeUploader(unittest.TestCase):
    def test_missing_client_secret_exits_with_code_1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing_cs = Path(tmp) / "missing_client_secret.json"
            missing_tok = Path(tmp) / "missing_token.json"
            with mock.patch.object(yu, "CLIENT_SECRET_PATH", missing_cs), \
                 mock.patch.object(yu, "TOKEN_PATH", missing_tok):
                with self.assertRaises(SystemExit) as ctx:
                    yu.YouTubeUploader()
                self.assertEqual(ctx.exception.code, 1)

    def test_upload_video_private_chunked_and_approval_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            cs_file = tmp_dir / "client_secret.json"
            tok_file = tmp_dir / "token.json"
            vid_file = tmp_dir / "final_short.mp4"
            pending_file = tmp_dir / "pending_approval.json"

            cs_file.write_text('{"installed":{"client_id":"cid","client_secret":"csec"}}', encoding="utf-8")
            tok_file.write_text(
                json.dumps({
                    "token": "ya29.test",
                    "refresh_token": "1//refresh",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "client_id": "cid",
                    "client_secret": "csec",
                    "scopes": [
                        "https://www.googleapis.com/auth/youtube.upload",
                        "https://www.googleapis.com/auth/youtube.force-ssl",
                    ],
                }),
                encoding="utf-8",
            )
            vid_file.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 4096)

            fake_status = mock.Mock()
            fake_status.progress.return_value = 0.5

            fake_insert_req = mock.Mock()
            fake_insert_req.next_chunk.side_effect = [
                (fake_status, None),
                (None, {"id": "YtReal987xyz"}),
            ]

            fake_update_req = mock.Mock()
            fake_update_req.execute.return_value = {"id": "YtReal987xyz", "status": {"privacyStatus": "public"}}

            fake_videos = mock.Mock()
            fake_videos.insert.return_value = fake_insert_req
            fake_videos.update.return_value = fake_update_req

            fake_service = mock.Mock()
            fake_service.videos.return_value = fake_videos

            with mock.patch.object(yu, "CLIENT_SECRET_PATH", cs_file), \
                 mock.patch.object(yu, "TOKEN_PATH", tok_file), \
                 mock.patch.object(yu, "PENDING_APPROVAL_PATH", pending_file), \
                 mock.patch.object(yu, "build", return_value=fake_service):
                uploader = yu.YouTubeUploader()
                video_id = uploader.upload_video_private(
                    vid_file,
                    title="Napolyon Tavşanlara Nasıl Yenildi? #Shorts",
                    description="Tarihin en ilginç olayı",
                    tags=["shorts", "tarih"],
                    category_id="27",
                )
                self.assertEqual(video_id, "YtReal987xyz")

                # insert çağrısının kesinlikle private olduğunu doğrula
                _, kwargs = fake_videos.insert.call_args
                self.assertEqual(kwargs["body"]["status"]["privacyStatus"], "private")
                self.assertFalse(kwargs["body"]["status"]["selfDeclaredMadeForKids"])

                # Onay kuyruğunu doğrula
                yu.save_pending_approval(video_id, "Napolyon Tavşanlara Nasıl Yenildi? #Shorts")
                pending_json = json.loads(pending_file.read_text(encoding="utf-8"))
                self.assertEqual(pending_json["YtReal987xyz"]["status"], "pending_approval")

                # Public onay akışını doğrula
                ok = uploader.make_video_public("YtReal987xyz")
                self.assertTrue(ok)
                _, u_kwargs = fake_videos.update.call_args
                self.assertEqual(u_kwargs["body"]["status"]["privacyStatus"], "public")


if __name__ == "__main__":
    unittest.main()
