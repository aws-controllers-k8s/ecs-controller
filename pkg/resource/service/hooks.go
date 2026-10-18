package service

import (
	"fmt"
	"time"

	"github.com/aws-controllers-k8s/ecs-controller/pkg/tags"
	ackrequeue "github.com/aws-controllers-k8s/runtime/pkg/requeue"
)

const (
	// These are not provided by the SDK.. another example of code we need
	// to generate.
	ServiceStatusActive       = "ACTIVE"
	ServiceStatusProvisioning = "PRIMARY"
	ServiceStatusInactive     = "INACTIVE"
	ServiceStatusDraining     = "DRAINING"
)

// Ideally, a part of this code needs to be generated.. However since the
// tags packge is not imported, we can't call it directly from sdk.go. We
// have to do this Go-fu to make it work.
var syncTags = tags.SyncTags

// requeueWaitWhileDraining is returned from sdkFind while a service drains,
// until DescribeServices reports it inactive and the resource reads as gone.
var requeueWaitWhileDraining = ackrequeue.NeededAfter(
	fmt.Errorf("service in '%s' state, requeuing until it is '%s'",
		ServiceStatusDraining, ServiceStatusInactive),
	5*time.Second,
)

// clusterActive returns true if the supplied cluster is in an active status
func clusterActive(r *resource) bool {
	if r.ko.Status.Status == nil {
		return false
	}
	cs := *r.ko.Status.Status
	return cs == ServiceStatusActive
}
