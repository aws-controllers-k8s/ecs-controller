// Copyright Amazon.com Inc. or its affiliates. All Rights Reserved.
//
// Licensed under the Apache License, Version 2.0 (the "License"). You may
// not use this file except in compliance with the License. A copy of the
// License is located at
//
//     http://aws.amazon.com/apache2.0/
//
// or in the "license" file accompanying this file. This file is distributed
// on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
// express or implied. See the License for the specific language governing
// permissions and limitations under the License.

// Code generated by ack-generate. DO NOT EDIT.

package service

import (
	"context"
	"fmt"

	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/types"
	"sigs.k8s.io/controller-runtime/pkg/client"

	iamapitypes "github.com/aws-controllers-k8s/iam-controller/apis/v1alpha1"
	ackv1alpha1 "github.com/aws-controllers-k8s/runtime/apis/core/v1alpha1"
	ackerr "github.com/aws-controllers-k8s/runtime/pkg/errors"
	acktypes "github.com/aws-controllers-k8s/runtime/pkg/types"

	svcapitypes "github.com/aws-controllers-k8s/ecs-controller/apis/v1alpha1"
)

// +kubebuilder:rbac:groups=iam.services.k8s.aws,resources=roles,verbs=get;list
// +kubebuilder:rbac:groups=iam.services.k8s.aws,resources=roles/status,verbs=get;list

// ClearResolvedReferences removes any reference values that were made
// concrete in the spec. It returns a copy of the input AWSResource which
// contains the original *Ref values, but none of their respective concrete
// values.
func (rm *resourceManager) ClearResolvedReferences(res acktypes.AWSResource) acktypes.AWSResource {
	ko := rm.concreteResource(res).ko.DeepCopy()

	if ko.Spec.ClusterRef != nil {
		ko.Spec.Cluster = nil
	}

	if ko.Spec.RoleRef != nil {
		ko.Spec.Role = nil
	}

	if ko.Spec.TaskDefinitionRef != nil {
		ko.Spec.TaskDefinition = nil
	}

	return &resource{ko}
}

// ResolveReferences finds if there are any Reference field(s) present
// inside AWSResource passed in the parameter and attempts to resolve those
// reference field(s) into their respective target field(s). It returns a
// copy of the input AWSResource with resolved reference(s), a boolean which
// is set to true if the resource contains any references (regardless of if
// they are resolved successfully) and an error if the passed AWSResource's
// reference field(s) could not be resolved.
func (rm *resourceManager) ResolveReferences(
	ctx context.Context,
	apiReader client.Reader,
	res acktypes.AWSResource,
) (acktypes.AWSResource, bool, error) {
	namespace := res.MetaObject().GetNamespace()
	ko := rm.concreteResource(res).ko

	resourceHasReferences := false
	err := validateReferenceFields(ko)
	if fieldHasReferences, err := rm.resolveReferenceForCluster(ctx, apiReader, namespace, ko); err != nil {
		return &resource{ko}, (resourceHasReferences || fieldHasReferences), err
	} else {
		resourceHasReferences = resourceHasReferences || fieldHasReferences
	}

	if fieldHasReferences, err := rm.resolveReferenceForRole(ctx, apiReader, namespace, ko); err != nil {
		return &resource{ko}, (resourceHasReferences || fieldHasReferences), err
	} else {
		resourceHasReferences = resourceHasReferences || fieldHasReferences
	}

	if fieldHasReferences, err := rm.resolveReferenceForTaskDefinition(ctx, apiReader, namespace, ko); err != nil {
		return &resource{ko}, (resourceHasReferences || fieldHasReferences), err
	} else {
		resourceHasReferences = resourceHasReferences || fieldHasReferences
	}

	return &resource{ko}, resourceHasReferences, err
}

// validateReferenceFields validates the reference field and corresponding
// identifier field.
func validateReferenceFields(ko *svcapitypes.Service) error {

	if ko.Spec.ClusterRef != nil && ko.Spec.Cluster != nil {
		return ackerr.ResourceReferenceAndIDNotSupportedFor("Cluster", "ClusterRef")
	}

	if ko.Spec.RoleRef != nil && ko.Spec.Role != nil {
		return ackerr.ResourceReferenceAndIDNotSupportedFor("Role", "RoleRef")
	}

	if ko.Spec.TaskDefinitionRef != nil && ko.Spec.TaskDefinition != nil {
		return ackerr.ResourceReferenceAndIDNotSupportedFor("TaskDefinition", "TaskDefinitionRef")
	}
	return nil
}

// resolveReferenceForCluster reads the resource referenced
// from ClusterRef field and sets the Cluster
// from referenced resource. Returns a boolean indicating whether a reference
// contains references, or an error
func (rm *resourceManager) resolveReferenceForCluster(
	ctx context.Context,
	apiReader client.Reader,
	namespace string,
	ko *svcapitypes.Service,
) (hasReferences bool, err error) {
	if ko.Spec.ClusterRef != nil && ko.Spec.ClusterRef.From != nil {
		hasReferences = true
		arr := ko.Spec.ClusterRef.From
		if arr.Name == nil || *arr.Name == "" {
			return hasReferences, fmt.Errorf("provided resource reference is nil or empty: ClusterRef")
		}
		obj := &svcapitypes.Cluster{}
		if err := getReferencedResourceState_Cluster(ctx, apiReader, obj, *arr.Name, namespace); err != nil {
			return hasReferences, err
		}
		ko.Spec.Cluster = (*string)(obj.Spec.Name)
	}

	return hasReferences, nil
}

// getReferencedResourceState_Cluster looks up whether a referenced resource
// exists and is in a ACK.ResourceSynced=True state. If the referenced resource does exist and is
// in a Synced state, returns nil, otherwise returns `ackerr.ResourceReferenceTerminalFor` or
// `ResourceReferenceNotSyncedFor` depending on if the resource is in a Terminal state.
func getReferencedResourceState_Cluster(
	ctx context.Context,
	apiReader client.Reader,
	obj *svcapitypes.Cluster,
	name string, // the Kubernetes name of the referenced resource
	namespace string, // the Kubernetes namespace of the referenced resource
) error {
	namespacedName := types.NamespacedName{
		Namespace: namespace,
		Name:      name,
	}
	err := apiReader.Get(ctx, namespacedName, obj)
	if err != nil {
		return err
	}
	var refResourceSynced, refResourceTerminal bool
	for _, cond := range obj.Status.Conditions {
		if cond.Type == ackv1alpha1.ConditionTypeResourceSynced &&
			cond.Status == corev1.ConditionTrue {
			refResourceSynced = true
		}
		if cond.Type == ackv1alpha1.ConditionTypeTerminal &&
			cond.Status == corev1.ConditionTrue {
			return ackerr.ResourceReferenceTerminalFor(
				"Cluster",
				namespace, name)
		}
	}
	if refResourceTerminal {
		return ackerr.ResourceReferenceTerminalFor(
			"Cluster",
			namespace, name)
	}
	if !refResourceSynced {
		return ackerr.ResourceReferenceNotSyncedFor(
			"Cluster",
			namespace, name)
	}
	if obj.Spec.Name == nil {
		return ackerr.ResourceReferenceMissingTargetFieldFor(
			"Cluster",
			namespace, name,
			"Spec.Name")
	}
	return nil
}

// resolveReferenceForRole reads the resource referenced
// from RoleRef field and sets the Role
// from referenced resource. Returns a boolean indicating whether a reference
// contains references, or an error
func (rm *resourceManager) resolveReferenceForRole(
	ctx context.Context,
	apiReader client.Reader,
	namespace string,
	ko *svcapitypes.Service,
) (hasReferences bool, err error) {
	if ko.Spec.RoleRef != nil && ko.Spec.RoleRef.From != nil {
		hasReferences = true
		arr := ko.Spec.RoleRef.From
		if arr.Name == nil || *arr.Name == "" {
			return hasReferences, fmt.Errorf("provided resource reference is nil or empty: RoleRef")
		}
		obj := &iamapitypes.Role{}
		if err := getReferencedResourceState_Role(ctx, apiReader, obj, *arr.Name, namespace); err != nil {
			return hasReferences, err
		}
		ko.Spec.Role = (*string)(obj.Status.ACKResourceMetadata.ARN)
	}

	return hasReferences, nil
}

// getReferencedResourceState_Role looks up whether a referenced resource
// exists and is in a ACK.ResourceSynced=True state. If the referenced resource does exist and is
// in a Synced state, returns nil, otherwise returns `ackerr.ResourceReferenceTerminalFor` or
// `ResourceReferenceNotSyncedFor` depending on if the resource is in a Terminal state.
func getReferencedResourceState_Role(
	ctx context.Context,
	apiReader client.Reader,
	obj *iamapitypes.Role,
	name string, // the Kubernetes name of the referenced resource
	namespace string, // the Kubernetes namespace of the referenced resource
) error {
	namespacedName := types.NamespacedName{
		Namespace: namespace,
		Name:      name,
	}
	err := apiReader.Get(ctx, namespacedName, obj)
	if err != nil {
		return err
	}
	var refResourceSynced, refResourceTerminal bool
	for _, cond := range obj.Status.Conditions {
		if cond.Type == ackv1alpha1.ConditionTypeResourceSynced &&
			cond.Status == corev1.ConditionTrue {
			refResourceSynced = true
		}
		if cond.Type == ackv1alpha1.ConditionTypeTerminal &&
			cond.Status == corev1.ConditionTrue {
			return ackerr.ResourceReferenceTerminalFor(
				"Role",
				namespace, name)
		}
	}
	if refResourceTerminal {
		return ackerr.ResourceReferenceTerminalFor(
			"Role",
			namespace, name)
	}
	if !refResourceSynced {
		return ackerr.ResourceReferenceNotSyncedFor(
			"Role",
			namespace, name)
	}
	if obj.Status.ACKResourceMetadata == nil || obj.Status.ACKResourceMetadata.ARN == nil {
		return ackerr.ResourceReferenceMissingTargetFieldFor(
			"Role",
			namespace, name,
			"Status.ACKResourceMetadata.ARN")
	}
	return nil
}

// resolveReferenceForTaskDefinition reads the resource referenced
// from TaskDefinitionRef field and sets the TaskDefinition
// from referenced resource. Returns a boolean indicating whether a reference
// contains references, or an error
func (rm *resourceManager) resolveReferenceForTaskDefinition(
	ctx context.Context,
	apiReader client.Reader,
	namespace string,
	ko *svcapitypes.Service,
) (hasReferences bool, err error) {
	if ko.Spec.TaskDefinitionRef != nil && ko.Spec.TaskDefinitionRef.From != nil {
		hasReferences = true
		arr := ko.Spec.TaskDefinitionRef.From
		if arr.Name == nil || *arr.Name == "" {
			return hasReferences, fmt.Errorf("provided resource reference is nil or empty: TaskDefinitionRef")
		}
		obj := &svcapitypes.TaskDefinition{}
		if err := getReferencedResourceState_TaskDefinition(ctx, apiReader, obj, *arr.Name, namespace); err != nil {
			return hasReferences, err
		}
		ko.Spec.TaskDefinition = (*string)(obj.Spec.Family)
	}

	return hasReferences, nil
}

// getReferencedResourceState_TaskDefinition looks up whether a referenced resource
// exists and is in a ACK.ResourceSynced=True state. If the referenced resource does exist and is
// in a Synced state, returns nil, otherwise returns `ackerr.ResourceReferenceTerminalFor` or
// `ResourceReferenceNotSyncedFor` depending on if the resource is in a Terminal state.
func getReferencedResourceState_TaskDefinition(
	ctx context.Context,
	apiReader client.Reader,
	obj *svcapitypes.TaskDefinition,
	name string, // the Kubernetes name of the referenced resource
	namespace string, // the Kubernetes namespace of the referenced resource
) error {
	namespacedName := types.NamespacedName{
		Namespace: namespace,
		Name:      name,
	}
	err := apiReader.Get(ctx, namespacedName, obj)
	if err != nil {
		return err
	}
	var refResourceSynced, refResourceTerminal bool
	for _, cond := range obj.Status.Conditions {
		if cond.Type == ackv1alpha1.ConditionTypeResourceSynced &&
			cond.Status == corev1.ConditionTrue {
			refResourceSynced = true
		}
		if cond.Type == ackv1alpha1.ConditionTypeTerminal &&
			cond.Status == corev1.ConditionTrue {
			return ackerr.ResourceReferenceTerminalFor(
				"TaskDefinition",
				namespace, name)
		}
	}
	if refResourceTerminal {
		return ackerr.ResourceReferenceTerminalFor(
			"TaskDefinition",
			namespace, name)
	}
	if !refResourceSynced {
		return ackerr.ResourceReferenceNotSyncedFor(
			"TaskDefinition",
			namespace, name)
	}
	if obj.Spec.Family == nil {
		return ackerr.ResourceReferenceMissingTargetFieldFor(
			"TaskDefinition",
			namespace, name,
			"Spec.Family")
	}
	return nil
}