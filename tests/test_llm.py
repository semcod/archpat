"""Protocol tests with a local HTTP stub, not real LLM-quality tests."""

from contextlib import contextmanager
import copy
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import unittest

from archpat.llm import MAX_RESPONSE_BYTES, normalize_story


STORY = {
    "id": "archive-story",
    "title": "Archiwizacja raportu",
    "actor": "operator",
    "goal": "Zarchiwizować raport po zakończeniu importu.",
    "acceptance_criteria": ["Archiwum ma przypisany identyfikator danych."],
    "operations": [{
        "id": "archive-report",
        "name": "Archiwizuj raport",
        "kind": "command",
        "capability": "archive",
        "aggregate": "report",
        "input_urns": ["urn:report:input"],
        "output_urns": ["urn:report:archive"],
        "temporal": {"text": "po zakończeniu importu", "resolution_status": "unresolved", "owner": "uritime"},
    }],
}


def completion(story):
    content = story if isinstance(story, str) else json.dumps(story, ensure_ascii=False)
    return json.dumps({"choices": [{"message": {"content": content}}]}, ensure_ascii=False).encode()


@contextmanager
def stub(responses):
    """responses are (HTTP status, bytes body, optional headers) tuples."""
    requests = []
    response_queue = list(responses)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, _format, *args):
            pass

        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            requests.append({"path": self.path, "headers": dict(self.headers), "body": json.loads(body)})
            status, content, headers = response_queue.pop(0) if response_queue else (500, b"", {})
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            for key, value in headers.items():
                self.send_header(key, value)
            self.end_headers()
            try:
                self.wfile.write(content)
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/v1", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


class LlmProtocolTests(unittest.TestCase):
    def test_valid_json_and_private_receipt(self):
        text = "Archiwizuj raport po zakończeniu importu."
        with stub([(200, completion(STORY), {})]) as (base_url, requests):
            story, receipt = normalize_story(
                text, base_url=base_url + "?access_token=query-secret", model="local-model", api_key="key-secret"
            )
        self.assertEqual("archive-story", story.id)
        self.assertEqual("unresolved", story.operations[0].temporal.resolution_status)
        self.assertEqual("po zakończeniu importu", story.operations[0].temporal.text)
        self.assertEqual(hashlib.sha256(text.encode()).hexdigest(), receipt["input_sha256"])
        self.assertTrue(receipt["schema_validated"])
        self.assertTrue(receipt["semantic_review_required"])
        self.assertEqual(1, receipt["attempts"])
        self.assertEqual(base_url + "/chat/completions", receipt["endpoint"])
        self.assertNotIn("secret", json.dumps(receipt))
        request = requests[0]
        self.assertEqual("/v1/chat/completions?access_token=query-secret", request["path"])
        self.assertEqual({"type": "json_object"}, request["body"]["response_format"])
        self.assertEqual("Bearer key-secret", request["headers"]["Authorization"])
        self.assertIn('"StorySpec"', request["body"]["messages"][0]["content"])

    def test_strict_type_failure_is_repaired_once(self):
        invalid = copy.deepcopy(STORY)
        invalid["constraints"] = {"max_processes": "2"}
        with stub([(200, completion(invalid), {}), (200, completion(STORY), {})]) as (url, requests):
            _, receipt = normalize_story("Archiwizuj raport.", base_url=url, model="test-model")
        self.assertEqual(2, receipt["attempts"])
        self.assertEqual(2, len(requests))
        self.assertIn("int_type", requests[1]["body"]["messages"][-1]["content"])

    def test_non_json_completion_can_be_repaired(self):
        with stub([(200, completion("not json"), {}), (200, completion(STORY), {})]) as (url, _):
            _, receipt = normalize_story("Archiwizuj raport.", base_url=url, model="test-model")
        self.assertEqual(2, receipt["attempts"])

    def test_validation_failure_has_no_keyword_fallback_or_prompt_dump(self):
        private_text = "private-user-story-content"
        with stub([(200, completion({"private": private_text}), {})] * 2) as (url, requests):
            with self.assertRaises(RuntimeError) as raised:
                normalize_story(private_text, base_url=url, model="test-model")
        self.assertEqual(2, len(requests))
        self.assertNotIn(private_text, str(raised.exception))
        self.assertIn("strict StorySpec", str(raised.exception))

    def test_http_errors_do_not_expose_credentials_or_body(self):
        secret = "key-never-print"
        with stub([(401, (secret + " private prompt").encode(), {})]) as (url, requests):
            with self.assertRaises(RuntimeError) as raised:
                normalize_story("private prompt", base_url=url, model="test-model", api_key=secret)
        self.assertEqual(1, len(requests))
        self.assertIn("HTTP 401", str(raised.exception))
        self.assertNotIn(secret, str(raised.exception))
        self.assertNotIn("private prompt", str(raised.exception))

    def test_response_limit_is_checked_with_and_without_content_length(self):
        for content, headers in (
            (b"{}", {"Content-Length": str(MAX_RESPONSE_BYTES + 1)}),
            (b"x" * (MAX_RESPONSE_BYTES + 1), {}),
        ):
            with self.subTest(headers=bool(headers)):
                with stub([(200, content, headers)]) as (url, requests):
                    with self.assertRaisesRegex(RuntimeError, "2 MiB"):
                        normalize_story("Archiwizuj raport.", base_url=url, model="test-model")
                self.assertEqual(1, len(requests))

    def test_single_attempt_rejects_invalid_reply(self):
        with stub([(200, completion({}), {}), (200, completion(STORY), {})]) as (url, requests):
            with self.assertRaises(RuntimeError):
                normalize_story("Archiwizuj raport.", base_url=url, model="test-model", max_attempts=1)
        self.assertEqual(1, len(requests))

    def test_deep_json_is_a_bounded_validation_failure(self):
        deep = "[" * 2000 + "]" * 2000
        with stub([(200, completion(deep), {})]) as (url, requests):
            with self.assertRaisesRegex(RuntimeError, "strict StorySpec"):
                normalize_story("Archiwizuj raport.", base_url=url, model="test-model", max_attempts=1)
        self.assertEqual(1, len(requests))

    def test_argument_bounds_are_checked_before_requests(self):
        with stub([]) as (url, requests):
            for changes in (
                {"text": ""}, {"text": "x" * 20_001}, {"model": ""},
                {"max_attempts": 0}, {"max_attempts": 3}, {"max_attempts": True},
                {"timeout": 31}, {"timeout": 0}, {"timeout": float("nan")},
                {"api_key": "private\r\nAuthorization: other"},
            ):
                arguments = {"text": "Archiwizuj raport.", "base_url": url, "model": "test-model"}
                arguments.update(changes)
                with self.subTest(field=list(changes)):
                    with self.assertRaises(ValueError):
                        normalize_story(**arguments)
        self.assertEqual([], requests)

    def test_redirect_is_not_followed(self):
        with stub([(200, completion(STORY), {})]) as (target, target_requests):
            with stub([(302, b"", {"Location": target + "/chat/completions"})]) as (url, requests):
                with self.assertRaisesRegex(RuntimeError, "HTTP 302"):
                    normalize_story("Archiwizuj raport.", base_url=url, model="test-model", api_key="private")
        self.assertEqual(1, len(requests))
        self.assertEqual([], target_requests)


if __name__ == "__main__":
    unittest.main()
