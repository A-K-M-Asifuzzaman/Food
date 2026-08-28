import assert from "node:assert/strict";
import { test } from "node:test";

import { forwardAuth, relay } from "../lib/upstream.ts";

function upstream(status: number, body: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function text(status: number, body: string): Response {
  return new Response(body, { status, headers: { "Content-Type": "text/html" } });
}

test("a success passes the payload straight through", async () => {
  const res = await relay(upstream(200, { recorded: true }), "Feedback");
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), { recorded: true });
});

test("an expired login stays a 401, not an outage", async () => {
  const res = await relay(upstream(401, { detail: "Sign in to use this endpoint." }), "Answer");
  assert.equal(res.status, 401);
  assert.deepEqual(await res.json(), { error: "Sign in to use this endpoint." });
});

test("a restricted console stays a 403", async () => {
  const res = await relay(upstream(403, { detail: "This console is restricted." }), "Analytics");
  assert.equal(res.status, 403);
  assert.deepEqual(await res.json(), { error: "This console is restricted." });
});

test("an oversized upload stays a 413", async () => {
  const res = await relay(upstream(413, { detail: "Image larger than 12 MB." }), "Model service");
  assert.equal(res.status, 413);
  assert.deepEqual(await res.json(), { error: "Image larger than 12 MB." });
});

test("an undecodable image stays a 415", async () => {
  const res = await relay(upstream(415, {}), "Model service");
  assert.equal(res.status, 415);
  assert.match((await res.json()).error, /could not be read as an image/);
});

test("a validation error reports the first message FastAPI gave", async () => {
  const detail = [{ loc: ["body", "question"], msg: "String should have at least 2 characters" }];
  const res = await relay(upstream(422, { detail }), "Answer");
  assert.equal(res.status, 422);
  assert.equal((await res.json()).error, "String should have at least 2 characters");
});

test("a 4xx with no usable body still keeps its status", async () => {
  const res = await relay(text(404, "<html>not found</html>"), "Model service");
  assert.equal(res.status, 404);
  assert.equal((await res.json()).error, "Model service rejected the request (404).");
});

test("an upstream crash is the one thing that becomes a 502", async () => {
  const res = await relay(upstream(500, { detail: "boom" }), "Model service");
  assert.equal(res.status, 502);
  assert.equal((await res.json()).error, "Model service returned 500.");
});

test("an upstream that is down also becomes a 502", async () => {
  const res = await relay(upstream(503, {}), "Answer");
  assert.equal(res.status, 502);
  assert.equal((await res.json()).error, "Answer returned 503.");
});

test("the caller's bearer token is forwarded, and nothing is invented", () => {
  const withToken = forwardAuth(
    new Request("https://example.test/", { headers: { authorization: "Bearer abc.def" } }),
    { "Content-Type": "application/json" },
  );
  assert.equal(withToken.get("authorization"), "Bearer abc.def");
  assert.equal(withToken.get("content-type"), "application/json");

  const without = forwardAuth(new Request("https://example.test/"));
  assert.equal(without.get("authorization"), null);
});
