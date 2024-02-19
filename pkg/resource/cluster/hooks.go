package cluster

import (
	"fmt"
	"time"

	"github.com/aws-controllers-k8s/ecs-controller/pkg/tags"
	ackrequeue "github.com/aws-controllers-k8s/runtime/pkg/requeue"
)

const (
	// These are not provided by the SDK.. another example of code we need
	// to generate.
	ClusterStatusActive         = "ACTIVE"
	ClusterStatusProvisioning   = "PROVISIONING"
	ClusterStatusDeprovisioning = "DEPROVISIONING"
	ClusterStatusFailed         = "FAILED"
	ClusterStatusInactive       = "INACTIVE"
)

// Ideally, a part of this code needs to be generated.. However since the
// tags packge is not imported, we can't call it directly from sdk.go. We
// have to do this Go-fu to make it work.
var syncTags = tags.SyncTags

// requeueWaitState returns a `ackrequeue.RequeueNeededAfter` struct
// explaining the cluster cannot be modified until it reaches an active status.
func requeueWaitStateActive(r *resource) *ackrequeue.RequeueNeededAfter {
	if r.ko.Status.Status == nil {
		return nil
	}
	return ackrequeue.NeededAfter(
		fmt.Errorf(
			"cluster in '%s' state, requeuing until cluster is '%s'",
			*r.ko.Status.Status, ClusterStatusActive,
		),
		time.Second*10,
	)
}

// clusterActive returns true if the supplied cluster is in an active status
func clusterActive(r *resource) bool {
	if r.ko.Status.Status == nil {
		return false
	}
	cs := *r.ko.Status.Status
	return cs == ClusterStatusActive
}
