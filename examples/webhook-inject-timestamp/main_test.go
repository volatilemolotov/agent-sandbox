// Copyright 2026 The Kubernetes Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package main

import (
	"bytes"
	"encoding/json"
	"net/http/httptest"
	"testing"
	"time"

	admissionv1 "k8s.io/api/admission/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/types"
)

type patchOp struct {
	Op    string      `json:"op"`
	Path  string      `json:"path"`
	Value interface{} `json:"value,omitempty"`
}

func admissionReviewRequest(t *testing.T, uid types.UID, rawObj interface{}) []byte {
	t.Helper()
	objBytes, err := json.Marshal(rawObj)
	if err != nil {
		t.Fatalf("failed to marshal raw object: %v", err)
	}
	ar := admissionv1.AdmissionReview{
		TypeMeta: metav1.TypeMeta{APIVersion: "admission.k8s.io/v1", Kind: "AdmissionReview"},
		Request: &admissionv1.AdmissionRequest{
			UID:       uid,
			Namespace: "default",
			Name:      "my-claim",
			Object:    runtime.RawExtension{Raw: objBytes},
		},
	}
	body, err := json.Marshal(ar)
	if err != nil {
		t.Fatalf("failed to marshal AdmissionReview: %v", err)
	}
	return body
}

func doMutate(t *testing.T, body []byte) (int, admissionv1.AdmissionReview) {
	t.Helper()
	req := httptest.NewRequest("POST", "/mutate", bytes.NewReader(body))
	w := httptest.NewRecorder()
	handleMutate(w, req)

	resp := w.Result()
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return resp.StatusCode, admissionv1.AdmissionReview{}
	}
	var ar admissionv1.AdmissionReview
	if err := json.NewDecoder(resp.Body).Decode(&ar); err != nil {
		t.Fatalf("failed to decode response body: %v", err)
	}
	return resp.StatusCode, ar
}

func decodePatch(t *testing.T, ar admissionv1.AdmissionReview) []patchOp {
	t.Helper()
	if len(ar.Response.Patch) == 0 {
		return nil
	}
	var ops []patchOp
	if err := json.Unmarshal(ar.Response.Patch, &ops); err != nil {
		t.Fatalf("failed to decode patch: %v", err)
	}
	return ops
}

func TestHandleMutate_EmptyBodyReturns400(t *testing.T) {
	status, _ := doMutate(t, nil)
	if status != 400 {
		t.Errorf("got status %d, want 400", status)
	}
}

func TestHandleMutate_InvalidJSONReturns400(t *testing.T) {
	status, _ := doMutate(t, []byte("not json"))
	if status != 400 {
		t.Errorf("got status %d, want 400", status)
	}
}

func TestHandleMutate_MissingRequestIsDenied(t *testing.T) {
	body, err := json.Marshal(admissionv1.AdmissionReview{
		TypeMeta: metav1.TypeMeta{APIVersion: "admission.k8s.io/v1", Kind: "AdmissionReview"},
	})
	if err != nil {
		t.Fatalf("failed to marshal AdmissionReview: %v", err)
	}

	status, ar := doMutate(t, body)
	if status != 200 {
		t.Fatalf("got HTTP status %d, want 200 (admission responses use 200 with Allowed=false)", status)
	}
	if ar.Response.Allowed {
		t.Error("expected Allowed=false when request is missing")
	}
	if ar.Response.Result == nil || ar.Response.Result.Message != "request is missing" {
		t.Errorf("got Result=%+v, want Message=\"request is missing\"", ar.Response.Result)
	}
}

func TestHandleMutate_MissingObjectIsDenied(t *testing.T) {
	ar := admissionv1.AdmissionReview{
		TypeMeta: metav1.TypeMeta{APIVersion: "admission.k8s.io/v1", Kind: "AdmissionReview"},
		Request: &admissionv1.AdmissionRequest{
			UID: types.UID("abc-123"),
			// Object.Raw intentionally left empty.
		},
	}
	body, err := json.Marshal(ar)
	if err != nil {
		t.Fatalf("failed to marshal AdmissionReview: %v", err)
	}

	status, resp := doMutate(t, body)
	if status != 200 {
		t.Fatalf("got HTTP status %d, want 200", status)
	}
	if resp.Response.Allowed {
		t.Error("expected Allowed=false when request object is missing")
	}
	if resp.Response.Result == nil || resp.Response.Result.Message != "request object is missing" {
		t.Errorf("got Result=%+v, want Message=\"request object is missing\"", resp.Response.Result)
	}
	// UID must still be echoed back even on denial.
	if resp.Response.UID != "abc-123" {
		t.Errorf("got UID=%q, want \"abc-123\"", resp.Response.UID)
	}
}

func TestHandleMutate_UnparseableObjectAdmitsWithoutMutating(t *testing.T) {
	// Written by hand rather than via admissionv1.AdmissionReview{}: the
	// outer envelope must stay valid JSON (so the top-level json.Unmarshal
	// in handleMutate succeeds) while "object" is a JSON value -- a string,
	// here -- that fails to unmarshal into the map[string]interface{}
	// handleMutate expects. runtime.RawExtension's own MarshalJSON rejects
	// exactly this kind of deliberately-mismatched raw payload, so it can't
	// be built by round-tripping through the real struct.
	corrupted := []byte(`{
		"apiVersion": "admission.k8s.io/v1",
		"kind": "AdmissionReview",
		"request": {
			"uid": "u1",
			"namespace": "default",
			"name": "my-claim",
			"object": "not an object"
		}
	}`)

	status, resp := doMutate(t, corrupted)
	if status != 200 {
		t.Fatalf("got HTTP status %d, want 200", status)
	}
	if !resp.Response.Allowed {
		t.Error("expected Allowed=true (admit without mutating) when the raw object can't be parsed")
	}
	if len(resp.Response.Patch) != 0 {
		t.Errorf("got a patch %s, want none when the raw object couldn't be parsed", resp.Response.Patch)
	}
}

func TestHandleMutate_AddsAnnotationsMapWhenAbsent(t *testing.T) {
	body := admissionReviewRequest(t, "u2", map[string]interface{}{
		"metadata": map[string]interface{}{"name": "my-claim"},
	})

	status, resp := doMutate(t, body)
	if status != 200 {
		t.Fatalf("got HTTP status %d, want 200", status)
	}
	if !resp.Response.Allowed {
		t.Fatal("expected Allowed=true")
	}
	if resp.Response.UID != "u2" {
		t.Errorf("got UID=%q, want \"u2\"", resp.Response.UID)
	}

	ops := decodePatch(t, resp)
	if len(ops) != 1 {
		t.Fatalf("got %d patch ops, want 1: %+v", len(ops), ops)
	}
	if ops[0].Op != "add" || ops[0].Path != "/metadata/annotations" {
		t.Fatalf("got op %+v, want add of /metadata/annotations", ops[0])
	}
	values, ok := ops[0].Value.(map[string]interface{})
	if !ok {
		t.Fatalf("got Value of type %T, want a map", ops[0].Value)
	}
	assertRecentRFC3339Nano(t, values[annotationKey])
}

func TestHandleMutate_AddsKeyWhenAnnotationsMapExistsWithoutKey(t *testing.T) {
	body := admissionReviewRequest(t, "u3", map[string]interface{}{
		"metadata": map[string]interface{}{
			"name":        "my-claim",
			"annotations": map[string]interface{}{"other-key": "other-value"},
		},
	})

	_, resp := doMutate(t, body)
	ops := decodePatch(t, resp)
	if len(ops) != 1 {
		t.Fatalf("got %d patch ops, want 1: %+v", len(ops), ops)
	}
	// "/" in the annotation key must be JSON-Pointer-escaped as "~1"
	// (RFC 6901), since it's a path segment here, not a separator.
	wantPath := "/metadata/annotations/agents.x-k8s.io~1webhook-first-observed-at"
	if ops[0].Op != "add" || ops[0].Path != wantPath {
		t.Fatalf("got op %+v, want add of %s", ops[0], wantPath)
	}
	assertRecentRFC3339Nano(t, ops[0].Value)
}

func TestHandleMutate_NoOpWhenAnnotationAlreadyPresent(t *testing.T) {
	body := admissionReviewRequest(t, "u4", map[string]interface{}{
		"metadata": map[string]interface{}{
			"name":        "my-claim",
			"annotations": map[string]interface{}{annotationKey: "2020-01-01T00:00:00Z"},
		},
	})

	status, resp := doMutate(t, body)
	if status != 200 {
		t.Fatalf("got HTTP status %d, want 200", status)
	}
	if !resp.Response.Allowed {
		t.Error("expected Allowed=true")
	}
	if len(resp.Response.Patch) != 0 {
		t.Errorf("got a patch %s, want none when the annotation is already present (must not clobber the original timestamp)", resp.Response.Patch)
	}
}

func assertRecentRFC3339Nano(t *testing.T, value interface{}) {
	t.Helper()
	s, ok := value.(string)
	if !ok {
		t.Fatalf("got value of type %T, want a string timestamp", value)
	}
	parsed, err := time.Parse(time.RFC3339Nano, s)
	if err != nil {
		t.Fatalf("value %q does not parse as RFC3339Nano: %v", s, err)
	}
	if since := time.Since(parsed); since < 0 || since > time.Minute {
		t.Errorf("timestamp %q is not recent (age %v)", s, since)
	}
}
