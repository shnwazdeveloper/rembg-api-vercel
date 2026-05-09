import base64
import unittest


from lib.rembg_api import APIError, _decode_base64_image


class RembgApiTests(unittest.TestCase):
    def test_decode_plain_base64_image(self):
        payload = base64.b64encode(b"image-bytes").decode("ascii")

        self.assertEqual(_decode_base64_image(payload), b"image-bytes")

    def test_decode_data_url_image(self):
        payload = base64.b64encode(b"image-bytes").decode("ascii")

        self.assertEqual(
            _decode_base64_image(f"data:image/png;base64,{payload}"), b"image-bytes"
        )

    def test_decode_invalid_base64_image(self):
        with self.assertRaises(APIError):
            _decode_base64_image("not-valid-base64")


if __name__ == "__main__":
    unittest.main()
