"""Regression checks for token claim verification after dependency updates."""
import time
import unittest

import jwt


class JwtVerificationGuardsTest(unittest.TestCase):
    key = "disposable-test-signing-key-32-bytes"

    def test_unsigned_peek_cannot_disable_later_claim_validation(self):
        token = jwt.encode({"sub": "fixture", "exp": int(time.time()) - 3600}, self.key, algorithm="HS256")
        options = {"verify_signature": False}
        jwt.decode(token, options=options)
        self.assertEqual(options, {"verify_signature": False})
        options["verify_signature"] = True
        with self.assertRaises(jwt.ExpiredSignatureError):
            jwt.decode(token, self.key, algorithms=["HS256"], options=options)

    def test_wrong_audience_is_rejected(self):
        token = jwt.encode({"sub": "fixture", "aud": "other-project"}, self.key, algorithm="HS256")
        with self.assertRaises(jwt.InvalidAudienceError):
            jwt.decode(token, self.key, algorithms=["HS256"], audience="collectra")

    def test_signature_allow_list_is_enforced(self):
        token = jwt.encode({"sub": "fixture"}, self.key, algorithm="HS256")
        with self.assertRaises(jwt.InvalidAlgorithmError):
            jwt.decode(token, self.key, algorithms=["HS512"])
