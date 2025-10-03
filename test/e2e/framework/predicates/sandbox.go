// Copyright 2025 The Kubernetes Authors.
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

package predicates

import (
	"fmt"

	"github.com/google/go-cmp/cmp"
	"github.com/google/go-cmp/cmp/cmpopts"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	sandboxv1alpha1 "sigs.k8s.io/agent-sandbox/api/v1alpha1"
	"sigs.k8s.io/controller-runtime/pkg/client"
)

func validateSandbox(obj client.Object) (*sandboxv1alpha1.Sandbox, error) {
	if obj == nil {
		return nil, fmt.Errorf("sandbox object is nil")
	}
	sandbox, ok := obj.(*sandboxv1alpha1.Sandbox)
	if !ok {
		return nil, fmt.Errorf("got %T, want %T", obj, &sandboxv1alpha1.Sandbox{})
	}
	return sandbox, nil
}

// SandboxHasStatus verifies that the Sandbox object has the specified status
func SandboxHasStatus(status sandboxv1alpha1.SandboxStatus) ObjectPredicate {
	return func(obj client.Object) error {
		sandbox, err := validateSandbox(obj)
		if err != nil {
			return err
		}
		opts := []cmp.Option{
			cmpopts.IgnoreFields(metav1.Condition{}, "LastTransitionTime"),
		}
		if diff := cmp.Diff(status, sandbox.Status, opts...); diff != "" {
			return fmt.Errorf("unexpected sandbox status (-want,+got):\n%s", diff)
		}
		return nil
	}
}
