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

package tags

import (
	"context"

	"github.com/aws-controllers-k8s/ecs-controller/apis/v1alpha1"
	ackrtlog "github.com/aws-controllers-k8s/runtime/pkg/runtime/log"

	"github.com/aws/aws-sdk-go/aws/request"
	svcsdk "github.com/aws/aws-sdk-go/service/ecs"
)

type metricsRecorder interface {
	RecordAPICall(opType string, opID string, err error)
}

type tagsClient interface {
	TagResourceWithContext(context.Context, *svcsdk.TagResourceInput, ...request.Option) (*svcsdk.TagResourceOutput, error)
	ListTagsForResourceWithContext(context.Context, *svcsdk.ListTagsForResourceInput, ...request.Option) (*svcsdk.ListTagsForResourceOutput, error)
	UntagResourceWithContext(context.Context, *svcsdk.UntagResourceInput, ...request.Option) (*svcsdk.UntagResourceOutput, error)
}

// syncTags examines the Tags in the supplied Resource and calls the
// TagResource and UntagResource APIs to ensure that the set of
// associated Tags stays in sync with the Resource.Spec.Tags
func SyncTags(
	ctx context.Context,
	client tagsClient,
	mr metricsRecorder,
	resourceID string,
	aTags []*v1alpha1.Tag,
	bTags []*v1alpha1.Tag,
) (err error) {
	rlog := ackrtlog.FromContext(ctx)
	exit := rlog.Trace("rm.syncTags")
	defer func() { exit(err) }()

	desiredTags := map[string]*string{}
	for _, t := range aTags {
		desiredTags[*t.Key] = t.Value
	}
	existingTags := map[string]*string{}
	for _, t := range bTags {
		existingTags[*t.Key] = t.Value
	}

	toAdd := map[string]*string{}
	toDelete := []*string{}

	for k, v := range desiredTags {
		if ev, found := existingTags[k]; !found || *ev != *v {
			toAdd[k] = v
		}
	}

	for k, _ := range existingTags {
		if _, found := desiredTags[k]; !found {
			deleteKey := k
			toDelete = append(toDelete, &deleteKey)
		}
	}

	if len(toAdd) > 0 {
		for k, v := range toAdd {
			rlog.Debug("adding tag to resource", "key", k, "value", *v)
		}
		if err = addTags(
			ctx,
			client,
			mr,
			resourceID,
			toAdd,
		); err != nil {
			return err
		}
	}
	if len(toDelete) > 0 {
		for _, k := range toDelete {
			rlog.Debug("removing tag from resource", "key", *k)
		}
		if err = removeTags(
			ctx,
			client,
			mr,
			resourceID,
			toDelete,
		); err != nil {
			return err
		}
	}

	return nil
}

// addTags adds the supplied Tags to the supplied resource
func addTags(
	ctx context.Context,
	client tagsClient,
	mr metricsRecorder,
	resourceARN string,
	tags map[string]*string,
) (err error) {
	rlog := ackrtlog.FromContext(ctx)
	exit := rlog.Trace("rm.addTag")
	defer func() { exit(err) }()

	sdkTags := []*svcsdk.Tag{}
	for k, v := range tags {
		sdkTags = append(sdkTags, &svcsdk.Tag{
			Key:   &k,
			Value: v,
		})
	}

	input := &svcsdk.TagResourceInput{
		ResourceArn: &resourceARN,
		Tags:        sdkTags,
	}

	_, err = client.TagResourceWithContext(ctx, input)
	mr.RecordAPICall("UPDATE", "TagResource", err)
	return err
}

// removeTags removes the supplied Tags from the supplied resource
func removeTags(
	ctx context.Context,
	client tagsClient,
	mr metricsRecorder,
	resourceARN string,
	tagKeys []*string, // the set of tag keys to delete
) (err error) {
	rlog := ackrtlog.FromContext(ctx)
	exit := rlog.Trace("rm.removeTag")
	defer func() { exit(err) }()

	input := &svcsdk.UntagResourceInput{
		ResourceArn: &resourceARN,
		TagKeys:     tagKeys,
	}
	_, err = client.UntagResourceWithContext(ctx, input)
	mr.RecordAPICall("UPDATE", "UntagResource", err)
	return err
}
