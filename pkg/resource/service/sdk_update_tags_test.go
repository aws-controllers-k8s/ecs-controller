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

package service

import (
	"context"
	"errors"
	"io"
	"net/http"
	"slices"
	"strings"
	"testing"

	ackv1alpha1 "github.com/aws-controllers-k8s/runtime/apis/core/v1alpha1"
	ackmetrics "github.com/aws-controllers-k8s/runtime/pkg/metrics"
	"github.com/aws/aws-sdk-go-v2/aws"
	svcsdk "github.com/aws/aws-sdk-go-v2/service/ecs"

	svcapitypes "github.com/aws-controllers-k8s/ecs-controller/apis/v1alpha1"
)

var errStubbedCall = errors.New("stubbed API call")

// recordingHTTPClient records the ECS operation of each request. TagResource
// and UntagResource succeed; every other operation fails with errStubbedCall.
type recordingHTTPClient struct {
	ops []string
}

func (c *recordingHTTPClient) Do(req *http.Request) (*http.Response, error) {
	target := req.Header.Get("X-Amz-Target")
	op := target[strings.LastIndex(target, ".")+1:]
	c.ops = append(c.ops, op)
	switch op {
	case "TagResource", "UntagResource":
		return &http.Response{
			StatusCode: http.StatusOK,
			Header:     http.Header{"Content-Type": []string{"application/x-amz-json-1.1"}},
			Body:       io.NopCloser(strings.NewReader("{}")),
			Request:    req,
		}, nil
	}
	return nil, errStubbedCall
}

func newTagsTestManager() (*resourceManager, *recordingHTTPClient) {
	httpClient := &recordingHTTPClient{}
	client := svcsdk.New(svcsdk.Options{
		Region:      "us-west-2",
		Credentials: aws.AnonymousCredentials{},
		HTTPClient:  httpClient,
		Retryer:     aws.NopRetryer{},
	})
	return &resourceManager{sdkapi: client, metrics: ackmetrics.NewMetrics("ecs")}, httpClient
}

func newServiceForTagsTest(desiredCount int64, tagValues map[string]string) *resource {
	arn := ackv1alpha1.AWSResourceName("arn:aws:ecs:us-west-2:111111111111:service/c/s")
	ko := &svcapitypes.Service{}
	ko.Spec.Name = aws.String("s")
	ko.Spec.Cluster = aws.String("c")
	ko.Spec.DesiredCount = aws.Int64(desiredCount)
	for k, v := range tagValues {
		ko.Spec.Tags = append(ko.Spec.Tags, &svcapitypes.Tag{Key: aws.String(k), Value: aws.String(v)})
	}
	ko.Status.ACKResourceMetadata = &ackv1alpha1.ResourceMetadata{ARN: &arn}
	return &resource{ko}
}

func TestSdkUpdate_OnlyTagsChanged_SkipsUpdateService(t *testing.T) {
	rm, httpClient := newTagsTestManager()
	desired := newServiceForTagsTest(1, map[string]string{"env": "prod", "team": "a"})
	latest := newServiceForTagsTest(1, map[string]string{"env": "dev", "old": "x"})
	delta := newResourceDelta(desired, latest)

	updated, err := rm.sdkUpdate(context.TODO(), desired, latest, delta)
	if err != nil {
		t.Fatalf("sdkUpdate returned error: %v", err)
	}
	want := []string{"TagResource", "UntagResource"}
	if !slices.Equal(httpClient.ops, want) {
		t.Errorf("API calls = %v, want %v", httpClient.ops, want)
	}
	if updated != desired {
		t.Errorf("sdkUpdate should return the desired resource when only tags changed")
	}
}

func TestSdkUpdate_TagsAndOtherFieldsChanged_CallsUpdateService(t *testing.T) {
	rm, httpClient := newTagsTestManager()
	desired := newServiceForTagsTest(2, map[string]string{"env": "prod"})
	latest := newServiceForTagsTest(1, map[string]string{"env": "dev"})
	delta := newResourceDelta(desired, latest)

	_, err := rm.sdkUpdate(context.TODO(), desired, latest, delta)
	if !errors.Is(err, errStubbedCall) {
		t.Fatalf("sdkUpdate error = %v, want the stubbed UpdateService error", err)
	}
	want := []string{"TagResource", "UpdateService"}
	if !slices.Equal(httpClient.ops, want) {
		t.Errorf("API calls = %v, want %v", httpClient.ops, want)
	}
}

func TestSdkUpdate_TagsUnchanged_DoesNotSyncTags(t *testing.T) {
	rm, httpClient := newTagsTestManager()
	desired := newServiceForTagsTest(2, map[string]string{"env": "prod"})
	latest := newServiceForTagsTest(1, map[string]string{"env": "prod"})
	delta := newResourceDelta(desired, latest)

	_, _ = rm.sdkUpdate(context.TODO(), desired, latest, delta)
	want := []string{"UpdateService"}
	if !slices.Equal(httpClient.ops, want) {
		t.Errorf("API calls = %v, want %v", httpClient.ops, want)
	}
}

func TestSdkUpdate_TagWithoutValue_DoesNotPanic(t *testing.T) {
	rm, httpClient := newTagsTestManager()
	desired := newServiceForTagsTest(1, map[string]string{"env": "prod"})
	desired.ko.Spec.Tags = append(desired.ko.Spec.Tags, &svcapitypes.Tag{Key: aws.String("novalue")})
	latest := newServiceForTagsTest(1, nil)
	latest.ko.Spec.Tags = []*svcapitypes.Tag{{Key: aws.String("env")}}
	delta := newResourceDelta(desired, latest)

	if _, err := rm.sdkUpdate(context.TODO(), desired, latest, delta); err != nil {
		t.Fatalf("sdkUpdate returned error: %v", err)
	}
	want := []string{"TagResource"}
	if !slices.Equal(httpClient.ops, want) {
		t.Errorf("API calls = %v, want %v", httpClient.ops, want)
	}
}
